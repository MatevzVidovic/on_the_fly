<?php
error_reporting(E_ALL & ~E_DEPRECATED & ~E_USER_DEPRECATED);
// Exercise the local dependency parser only. No application boot or DB access.
require __DIR__ . '/../../symlinks/fmp/vendor/autoload.php';
set_error_handler(function ($severity, $message, $file, $line) {
    if (!(error_reporting() & $severity)) return false;
    throw new ErrorException($message, 0, $severity, $file, $line);
});
$paths = [
    'ordinary_joins' => __DIR__ . '/../mv-backup/pripis_standardne_statistike_napak.lift-compatible-select.sql',
    'postgres_export' => __DIR__ . '/../mv-backup/pripis_standardne_statistike_napak.select.sql',
    'lift_original' => __DIR__ . '/../mv-backup/pripis_standardne_statistike_napak.lift-select.sql',
    'create_statement' => __DIR__ . '/../mv-backup/02_create_pripis_standardne_statistike_napak_simple.sql',
];
$report = [];
foreach ($paths as $name => $path) {
    try {
        $service = new Gms\Util\Services\ParseSqlInfoUtilityService(new PHPSQLParser\PHPSQLParser());
        $info = $service->handle(file_get_contents($path));
        $report[$name] = ['parsed' => true, 'info' => $info];
    } catch (Throwable $error) {
        $report[$name] = ['parsed' => false, 'message' => $error->getMessage(), 'file' => str_replace(dirname(__DIR__, 2).'/', '', $error->getFile()), 'line' => $error->getLine()];
    }
}
file_put_contents(__DIR__.'/../mv-backup/lift-parser-check.json', json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)."\n");
echo json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES)."\n";
