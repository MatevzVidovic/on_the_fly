<?php

date_default_timezone_set('UTC'); // Assumption: same default as FMP's config/app.php.
$watermark = '2026-10-06 15:01:29';

// Exact FMP expression and DATE_TIME_FORMAT value.
// $minDate = (new DateTime($attributeTableIntegration->last_changed_datetime))->format(AttributeTableIntegrationConstants::DATE_TIME_FORMAT);
$minDate = (new DateTime($watermark))->format('Y-m-d H:i:s.uP');

echo "PHP timezone: " . date_default_timezone_get() . "\n";
echo "Stored value: $watermark\n";
echo "Oracle bound: $minDate\n";
