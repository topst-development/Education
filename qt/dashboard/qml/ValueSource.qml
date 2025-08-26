import QtQuick 2.2
import QtQuick.Window 2.1
import QtQuick.Controls 1.4
import QtQuick.Controls.Styles 1.4
import QtQuick.Extras 1.4
Item {
    id: valueSource
    property bool useRealData: true
    property real kph: 0
    property real rpm: 1
    property real fuel: 0.85
    Connections {
        target: tcpClient
        onTelemetryUpdated: function(rpm0to6, speedKmh, fuelL, steering) {
            if (useRealData) {
                kph  = speedKmh
                rpm  = rpm0to6
                fuel = Math.max(0, Math.min(1, fuelL / 1400.0))
            }
        }
    }

    SequentialAnimation {
        running: !useRealData
        loops: Animation.Infinite


    }
}
