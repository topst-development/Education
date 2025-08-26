// main.cpp
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QTcpSocket>
#include <QByteArray>
#include <QDebug>
#include <QtGui/QFont>
#include <QtGui/QFontDatabase>
#include <QJsonDocument>
#include <QJsonObject>

class TcpClient : public QObject {
    Q_OBJECT
public:
    explicit TcpClient(QObject* parent=nullptr) : QObject(parent) {
        connect(&socket, &QTcpSocket::connected, this, []{
            qDebug() << u8"서버에 연결 성공!";
        });
        connect(&socket, &QTcpSocket::disconnected, this, []{
            qDebug() << u8"서버와 연결이 끊어졌습니다.";
        });
        connect(&socket, &QTcpSocket::readyRead, this, &TcpClient::onReadyRead);
        socket.connectToHost("127.0.0.1", 9999);
    }

signals:
    void telemetryUpdated(double rpm, double speedKmh, double fuelL, double steering);

private slots:
    void onReadyRead() {
        buf_.append(socket.readAll());
        int idx;
        while ((idx = buf_.indexOf('\n')) != -1) {
            const QByteArray line = buf_.left(idx);
            buf_.remove(0, idx + 1);
            handleLine(line.trimmed());
        }
    }

private:
    void handleLine(const QByteArray& line) {
        if (line.isEmpty()) return;
        if (line[0] != '{' && line[0] != '[') {
            qDebug().noquote() << "RX(non-JSON):" << line;
            return;
        }

        QJsonParseError err;
        const QJsonDocument doc = QJsonDocument::fromJson(line, &err);
        if (err.error != QJsonParseError::NoError || !doc.isObject()) {
            qDebug() << "JSON parse error:" << err.errorString() << "data=" << line.left(120);
            return;
        }

        const QJsonObject o = doc.object();
        const double rpm   = o.value("rpm").toDouble();
        const double speed = o.value("speed_kmh").toDouble();
        const double fuel  = o.value("fuel_l").toDouble();
        const double steer = o.value("steering").toDouble();
        emit telemetryUpdated(rpm, speed, fuel, steer);
    }

    QTcpSocket socket;
    QByteArray buf_;
};



int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);

    QFontDatabase::addApplicationFont(":/fonts/DejaVuSans.ttf");
    app.setFont(QFont("DejaVu Sans"));

    TcpClient client;

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("tcpClient", &client);
    engine.load(QUrl(QStringLiteral("qrc:/qml/dashboard.qml")));
    if (engine.rootObjects().isEmpty())
        return -1;

    return app.exec();
}

#include "main.moc"
