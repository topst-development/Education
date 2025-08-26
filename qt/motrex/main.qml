import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Scene3D 2.12
import Qt3D.Core 2.12
import Qt3D.Render 2.12
import Qt3D.Input 2.12
import Qt3D.Extras 2.12

ApplicationWindow {
    id: win
    width: 800
    height: 400
    visible: true
    title: "Lane 3D Demo"

    // 기존 Item의 속성/함수 그대로 옮김
    property string lane1Message: ""
    property string lane2Message: ""
    property string lane3Message: ""

    property real yaw: 0
    property real pitch: 10
    property real zoom: 30
    property var laneX: [-7.5, -2.5, 2.5, 7.5]

    function updateCameraPosition() {
        let radYaw = yaw * Math.PI / 180
        let radPitch = pitch * Math.PI / 180
        let x = zoom * Math.sin(radYaw) * Math.cos(radPitch)
        let y = zoom * Math.sin(radPitch)
        let z = zoom * Math.cos(radYaw) * Math.cos(radPitch)
        camera.position = Qt.vector3d(x, y, z)
    }

    // C++에서 setContextProperty("tcpClient", &client) 한 객체의 신호 받기
    Connections {
        target: tcpClient
        function onShowCarsForLane(lane) {
            if (lane === 1) { carModel1.source = "qrc:/icons/test.obj"; hideTimer1.start() }
            else if (lane === 2) { carModel2.source = "qrc:/icons/test.obj"; hideTimer2.start() }
            else if (lane === 3) { carModel3.source = "qrc:/icons/test.obj"; hideTimer3.start() }
            else if (lane === 4) { carModel4.source = "qrc:/icons/test.obj"; hideTimer4.start() }
            else if (lane === 5) { carModel5.source = "qrc:/icons/test.obj"; hideTimer5.start() }
        }
    }

    // 화면 채우도록 래퍼
    Item {
        anchors.fill: parent

        Scene3D {
            anchors.fill: parent
            aspects: ["input", "logic", "render"]

            Entity {
                id: rootEntity

                Camera {
                    id: camera
                    position: Qt.vector3d(0, 20, 40)
                    viewCenter: Qt.vector3d(0, 0, 0)
                    upVector: Qt.vector3d(0, 1, 0)
                }

                components: [
                    RenderSettings {
                        activeFrameGraph: ForwardRenderer {
                            camera: camera
                            clearColor: "#1a1a1a"
                        }
                    },
                    InputSettings {}
                ]

                // 조명
                Entity {
                    components: [
                        PointLight { color: "white"; intensity: 3; constantAttenuation: 1.0 },
                        Transform { translation: Qt.vector3d(0, 10, 10) }
                    ]
                }

                // 도로
                Entity {
                    components: [
                        PlaneMesh { width: 20; height: 80 },
                        PhongMaterial { diffuse: "#303030"; shininess: 10; specular: "#555555" },
                        Transform { rotation: fromAxisAndAngle(Qt.vector3d(1, 0, 0), 0); translation: Qt.vector3d(0, -1.0, 0) }
                    ]
                }

                // 차선 4개
                Entity { components: [ CuboidMesh { xExtent: 0.3; yExtent: 0.2; zExtent: 60 }, PhongMaterial { diffuse: "white" }, Transform { translation: Qt.vector3d(-7.5, -1.0, -10) } ] }
                Entity { components: [ CuboidMesh { xExtent: 0.3; yExtent: 0.2; zExtent: 60 }, PhongMaterial { diffuse: "white" }, Transform { translation: Qt.vector3d(-2.5, -1.0, -10) } ] }
                Entity { components: [ CuboidMesh { xExtent: 0.3; yExtent: 0.2; zExtent: 60 }, PhongMaterial { diffuse: "white" }, Transform { translation: Qt.vector3d( 2.5, -1.0, -10) } ] }
                Entity { components: [ CuboidMesh { xExtent: 0.3; yExtent: 0.2; zExtent: 60 }, PhongMaterial { diffuse: "white" }, Transform { translation: Qt.vector3d( 7.5, -1.0, -10) } ] }

                // 자차
                Entity {
                    components: [
                        SceneLoader {
                            id: carModel_my
                            source: "qrc:/icons/test.obj"
                            onStatusChanged: {
                                if (status === SceneLoader.Ready) console.log("자차 모델 로드 완료")
                                else if (status === SceneLoader.Error) console.error("자차 모델 로드 실패")
                            }
                        },
                        Transform {
                            translation: Qt.vector3d(0, -0.9, 13)
                            scale3D: Qt.vector3d(0.03, 0.03, 0.03)
                            rotation: fromAxisAndAngle(Qt.vector3d(0, 1, 0), 90)
                        }
                    ]
                }

                // 주변 차량들(초기엔 비어 있다가 신호 오면 표시)
                Entity { components: [ SceneLoader { id: carModel1; source: "" }, Transform { translation: Qt.vector3d(-4.8, -1, -20); scale3D: Qt.vector3d(0.03,0.03,0.03); rotation: fromAxisAndAngle(Qt.vector3d(0,1,0), -90) } ] }
                Entity { components: [ SceneLoader { id: carModel2; source: "" }, Transform { translation: Qt.vector3d(-4.8, -1,   2); scale3D: Qt.vector3d(0.03,0.03,0.03); rotation: fromAxisAndAngle(Qt.vector3d(0,1,0), -90) } ] }
                Entity { components: [ SceneLoader { id: carModel3; source: "" }, Transform { id: carTransform_1; translation: Qt.vector3d( 4.8, -1,   2); scale3D: Qt.vector3d(0.03,0.03,0.03); rotation: fromAxisAndAngle(Qt.vector3d(0,1,0),  90) } ] }
                Entity { components: [ SceneLoader { id: carModel4; source: "" }, Transform { id: carTransform_2; translation: Qt.vector3d( 4.8, -1, -20); scale3D: Qt.vector3d(0.03,0.03,0.03); rotation: fromAxisAndAngle(Qt.vector3d(0,1,0),  90) } ] }
                Entity { components: [ SceneLoader { id: carModel5; source: "" }, Transform { translation: Qt.vector3d(0, -0.9, -5); scale3D: Qt.vector3d(0.03,0.03,0.03); rotation: fromAxisAndAngle(Qt.vector3d(0,1,0),  90) } ] }

                // 표시 후 1초 뒤 감추는 타이머들
                Timer { id: hideTimer1; interval: 1000; repeat: false; onTriggered: carModel1.source = "" }
                Timer { id: hideTimer2; interval: 1000; repeat: false; onTriggered: carModel2.source = "" }
                Timer { id: hideTimer3; interval: 1000; repeat: false; onTriggered: carModel3.source = "" }
                Timer { id: hideTimer4; interval: 1000; repeat: false; onTriggered: carModel4.source = "" }
                Timer { id: hideTimer5; interval: 1000; repeat: false; onTriggered: carModel5.source = "" }
            }
        }
    }

    Component.onCompleted: updateCameraPosition()
}
