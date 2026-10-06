<?php

use Gms\AttributeTables\Constants\AttributeTableIntegrationConstants;
use Gms\AttributeTables\Managers\AttributeTableIntegrationManager;
use Gms\AttributeTables\Models\AttributeTableIntegrationGmsModel;
use Gms\AttributeTables\Services\Facade\AttributeTableIntegration\Processing\Sql\ProcessSqlDeltaIntegrationFacadeService;
use Gms\Util\Context\UserContext;
use Illuminate\Database\Capsule\Manager as Capsule;
use Illuminate\Events\Dispatcher;

require_once __DIR__ . '/WatermarkRoundTripTest.php';

/** Local disposable PostgreSQL only. Never uses .env or application bootstrap. */
final class WatermarkPersistenceTest extends WatermarkRoundTripTest
{
    public function testRealModelSaveReloadAndNextDeltaCutoff(): void
    {
        $previousTimezone = date_default_timezone_get();
        $previousResolver = AttributeTableIntegrationGmsModel::getConnectionResolver();
        date_default_timezone_set('UTC');
        $db = new Capsule();
        $db->addConnection([
            'driver' => 'pgsql', 'host' => '127.0.0.1', 'port' => 55439,
            'database' => 'watermark_test', 'username' => 'watermark_test',
            'password' => 'local-test-only', 'charset' => 'utf8', 'prefix' => '',
        ]);
        $db->setEventDispatcher(new Dispatcher());
        $db->bootEloquent();
        $connection = $db->getConnection();
        $connection->beginTransaction();
        try {
            // TEMP table shadows the model's normal table for this connection only.
            $connection->statement('CREATE TEMP TABLE attribute_table_integrations (
                id text PRIMARY KEY, last_changed_datetime timestamp(6) without time zone,
                created_at timestamp, updated_at timestamp, updated_by text) ON COMMIT DROP');
            $connection->table('attribute_table_integrations')->insert(['id' => 'example']);

            // Real maximum-date handling; same formatting used by delta handle() on return.
            $processor = $this->getMockBuilder(ProcessSqlDeltaIntegrationFacadeService::class)
                ->disableOriginalConstructor()->onlyMethods([])->getMock();
            $maximum = null;
            $args = ['2026-08-05 12:26:56.000000+02:00', &$maximum];
            (new ReflectionMethod($processor, 'setChangeDate'))->invokeArgs($processor, $args);
            $outgoing = $maximum->format(AttributeTableIntegrationConstants::DATE_TIME_FORMAT);
            $connection->listen(function ($query) use ($outgoing): void {
                if (in_array($outgoing, $query->bindings, true)) {
                    fwrite(STDOUT, "Actual UPDATE binding: $outgoing\n");
                }
            });

            // Real persistence manager/model; only the user's identity is mocked.
            $user = $this->createMock(UserContext::class);
            $user->method('getUserId')->willReturn('diagnostic-user');
            $manager = new AttributeTableIntegrationManager(new AttributeTableIntegrationGmsModel());
            $manager->setUserContext($user);
            $manager->update('example', ['last_changed_datetime' => $outgoing]);
            $stored = AttributeTableIntegrationGmsModel::findOrFail('example')->last_changed_datetime;
            fwrite(STDOUT, "Reloaded from PostgreSQL: $stored\n");

            // Runs real delta handle() and asserts the next cutoff preserves the instant.
            $this->checkCutoff($stored);
        } finally {
            $connection->rollBack();
            $connection->disconnect();
            if ($previousResolver === null) {
                AttributeTableIntegrationGmsModel::unsetConnectionResolver();
            } else {
                AttributeTableIntegrationGmsModel::setConnectionResolver($previousResolver);
            }
            date_default_timezone_set($previousTimezone);
        }
    }
}
