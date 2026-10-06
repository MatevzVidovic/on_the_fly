<?php

use Gms\AttributeTables\Services\Facade\AttributeTableIntegration\Processing\Sql\ProcessSqlDeltaIntegrationFacadeService;
use PHPUnit\Framework\TestCase;
use Symfony\Component\Console\Output\NullOutput;

/** Runs the real handle() up to its cutoff log, before any Oracle call or write. */
class WatermarkRoundTripTest extends TestCase
{
    public function testNaivePostgresWatermarkMustPreserveTheSourceInstant(): void
    {
        // Fixture established by the earlier read-only PostgreSQL cast probe.
        $this->checkCutoff('2026-08-05 12:26:56');
    }

    public function testOffsetPreservedControl(): void
    {
        $this->checkCutoff('2026-08-05 12:26:56.000000+02:00');
    }

    public function testConvertedToUtcBeforeStorageControl(): void
    {
        $this->checkCutoff('2026-08-05 10:26:56');
    }

    protected function checkCutoff(string $watermark): void
    {
        $timezone = date_default_timezone_get();
        date_default_timezone_set('UTC');
        try {
            // Replace surrounding metadata, logging and Temporal dependencies only.
            // handle() and its watermark parsing/formatting remain FMP's real code.
            $service = $this->getMockBuilder(ProcessSqlDeltaIntegrationFacadeService::class)
                ->disableOriginalConstructor()
                ->onlyMethods(['fetchAttributeTable', 'fetchAttributeFieldIntegrations', 'heartbeatDelta', 'log'])
                ->getMock();
            $service->setOutput(new NullOutput());
            $service->method('fetchAttributeTable')->willReturn((object) []);
            $service->method('fetchAttributeFieldIntegrations')->willReturn([
                'last_sync_field' => (object) ['api_name' => 'DATUM_SYS'],
                'api_key_column_name' => 'DEL_STAVBE_H_ID',
            ]);
            $cutoff = null;
            $stop = new RuntimeException('Captured cutoff; stop before remote query');
            $service->method('log')->willReturnCallback(
                function ($id, $type, $message) use (&$cutoff, $stop): void {
                    if (preg_match('/\[min_date = (.*?), max_date = /', $message, $match)) {
                        $cutoff = $match[1];
                        throw $stop;
                    }
                }
            );
            try {
                $service->handle((object) [
                    'attribute_table_integration_id' => 'diagnostic-only',
                    'attribute_table_id' => 'diagnostic-only',
                    'last_sync_start' => '2026-08-05 10:36:25',
                    'last_changed_datetime' => $watermark,
                    'use_changed_datetime_for_delta' => true,
                    'params' => (object) [],
                ], '2026-08-08 02:50:00.000000+00:00');
                self::fail('Did not intercept the cutoff; recheck the test seam');
            } catch (RuntimeException $exception) {
                if ($exception !== $stop) {
                    throw $exception;
                }
            }
            self::assertNotNull($cutoff);
            fwrite(STDOUT, "Next FMP cutoff: $cutoff\n");
            $sql = (new \Gms\AttributeTables\Services\Util\Sql\Manager\OracleSqlManagerService())
                ->wrapFilters('SELECT DATUM_SYS FROM nep.DELI_STAVB_H', [
                    ['name' => 'DATUM_SYS', 'operator' => '>=', 'value' => ':last_sync_start'],
                ]);
            fwrite(STDOUT, "Actual Oracle filter: $sql\n");
            $expected = new DateTimeImmutable('2026-08-05 12:26:56+02:00');
            $actual = new DateTimeImmutable($cutoff);
            self::assertSame($expected->getTimestamp(), $actual->getTimestamp(),
                "FMP cutoff=$cutoff; shift=" . ($actual->getTimestamp() - $expected->getTimestamp()) . ' seconds');
        } finally {
            date_default_timezone_set($timezone);
        }
    }
}
