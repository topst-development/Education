#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QTcpSocket>
#include <QTimer>
#include <QQmlContext>
#include <QDebug>
#include <QtGui/QFont>
#include <QtGui/QFontDatabase>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QCommandLineParser>
#include <QCommandLineOption>

class TcpClient : public QObject {
    Q_OBJECT
public:
    TcpClient() {
        connect(&socket, &QTcpSocket::connected, this, [](){
            qDebug() << "✅ 서버에 연결 성공!";
        });
        connect(&socket, &QTcpSocket::disconnected, this, [](){
            qDebug() << "⚠️ 서버와 연결이 끊어졌습니다.";
        });
        connect(&socket, &QTcpSocket::readyRead, this, &TcpClient::checkForData);
    }

    Q_INVOKABLE void connectTo(const QString& ip, int port) {
        if (socket.isOpen() || socket.state() == QAbstractSocket::ConnectingState)
            socket.disconnectFromHost();
        qDebug() << "➡️  서버 접속 시도:" << ip << port;
        socket.connectToHost(ip, port);
    }

    void connectFromConfig() {
        QFile file(":/icons/config.json");   // qrc 기본값
        if (file.open(QIODevice::ReadOnly)) {
            auto json = QJsonDocument::fromJson(file.readAll()).object();
            const QString ip = json.value("server_ip").toString();
            const int port   = json.value("server_port").toInt();
            connectTo(ip, port);
        } else {
            qWarning() << "config.json(qrc) 열기 실패";
        }
    }

signals:
    void showCarsForLane(int lane);   // lane 번호 전달

private slots:
    void checkForData() {
        if (socket.bytesAvailable() > 0) {
            QByteArray data = socket.readAll();

            if (data.contains("object_detected_lane_1")) emit showCarsForLane(1);
            if (data.contains("object_detected_lane_2")) emit showCarsForLane(2);
            if (data.contains("object_detected_lane_3")) emit showCarsForLane(3);
            if (data.contains("object_detected_lane_4")) emit showCarsForLane(4);
            if (data.contains("object_detected_lane_5")) emit showCarsForLane(5);
        }
    }

private:
    QTcpSocket socket;
    QTimer timer;
};

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);

    // --- 커맨드라인 파서 설정 ---
    QCommandLineParser parser;
    parser.setApplicationDescription("Lane telemetry client");
    parser.addHelpOption();
    QCommandLineOption ipOpt({"i","ip"}, "Server IP address", "ip");
    QCommandLineOption portOpt({"p","port"}, "Server port", "port");
    parser.addOption(ipOpt);
    parser.addOption(portOpt);
    parser.process(app);

    QQmlApplicationEngine engine;
    QFontDatabase::addApplicationFont(":/fonts/DejaVuSans.ttf");
    app.setFont(QFont("DejaVu Sans"));

    TcpClient client;
    engine.rootContext()->setContextProperty("tcpClient", &client);

    // 인자 우선, 없으면 qrc 설정 사용
    const QString ipArg = parser.value(ipOpt);
    bool ok = false;
    int portArg = parser.value(portOpt).toInt(&ok);
    if (!ipArg.isEmpty() && ok && portArg > 0) {
        client.connectTo(ipArg, portArg);
    } else {
        client.connectFromConfig();
    }

    engine.load(QUrl(QStringLiteral("qrc:/main.qml")));
    return app.exec();
}

#include "main.moc"
