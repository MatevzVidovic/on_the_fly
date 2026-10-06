<?php

use Gms\AttributeTables\Constants\AttributeTableIntegrationConstants;
use PHPUnit\Framework\TestCase;

final class WatermarkTimezoneTest extends TestCase
{
    public function testSavedWatermarkMustNotMoveTheNextCutoffForward(): void
    {
        $previousTimezone = date_default_timezone_get();
        date_default_timezone_set('UTC'); // FMP config/app.php default.

        try {
            // Oracle FROM_TZ(..., 'Europe/Ljubljana') returns this source instant.
            $sourceWatermark = new DateTime('2026-08-05 14:00:00+02:00');

            // Fixture: the value returned from timestamp WITHOUT time zone storage.
            $integration = (object) ['last_changed_datetime' => '2026-08-05 14:00:00'];

            // Exact expression from ProcessSqlDeltaIntegrationFacadeService::handle().
            $minDate = (new DateTime($integration->last_changed_datetime))
                ->format(AttributeTableIntegrationConstants::DATE_TIME_FORMAT);

            // The next lower bound must represent the SAME instant as the last import.
            self::assertSame(
                $sourceWatermark->getTimestamp(),
                (new DateTime($minDate))->getTimestamp(),
                "Source watermark: 14:00+02:00. FMP cutoff: $minDate. " .
                'FMP starts at 16:00 Ljubljana and skips the 14:00–16:00 interval.'
            );
        } finally {
            date_default_timezone_set($previousTimezone);
        }
    }
}
