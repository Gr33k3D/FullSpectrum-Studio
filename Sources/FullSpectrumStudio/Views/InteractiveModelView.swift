import AppKit
import SceneKit
import SwiftUI

struct InteractiveModelView: NSViewRepresentable {
    let meshURL: URL
    let resetToken: Int

    final class Coordinator {
        var meshURL: URL?
        var resetToken = -1
        var homeTransform: SCNMatrix4?
        var target = SCNVector3Zero
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    func makeNSView(context: Context) -> SCNView {
        let view = SCNView()
        view.wantsLayer = true
        view.layer?.backgroundColor = NSColor.clear.cgColor
        view.backgroundColor = .clear
        view.allowsCameraControl = true
        view.autoenablesDefaultLighting = false
        view.antialiasingMode = .multisampling4X
        view.preferredFramesPerSecond = 60
        return view
    }

    func updateNSView(_ view: SCNView, context: Context) {
        if context.coordinator.meshURL != meshURL {
            loadScene(in: view, coordinator: context.coordinator)
            context.coordinator.meshURL = meshURL
        }
        if context.coordinator.resetToken != resetToken {
            resetCamera(in: view, coordinator: context.coordinator, animated: true)
            context.coordinator.resetToken = resetToken
        }
    }

    private func loadScene(in view: SCNView, coordinator: Coordinator) {
        guard let scene = try? SCNScene(url: meshURL, options: nil) else {
            return
        }
        scene.background.contents = NSColor.clear
        scene.rootNode.enumerateChildNodes { node, _ in
            node.geometry?.materials.forEach { material in
                material.lightingModel = .physicallyBased
                material.roughness.contents = 0.72
                material.metalness.contents = 0.0
                material.isDoubleSided = true
            }
        }

        let (minimum, maximum) = scene.rootNode.boundingBox
        let center = SCNVector3(
            (minimum.x + maximum.x) / 2,
            (minimum.y + maximum.y) / 2,
            (minimum.z + maximum.z) / 2
        )
        let span = max(maximum.x - minimum.x, max(maximum.y - minimum.y, maximum.z - minimum.z))
        let radius = max(span / 2, 1)

        let cameraNode = SCNNode()
        let camera = SCNCamera()
        camera.fieldOfView = 42
        camera.zNear = Double(max(radius * 0.002, 0.01))
        camera.zFar = Double(radius * 40)
        cameraNode.camera = camera
        cameraNode.position = SCNVector3(
            center.x + radius * 1.8,
            center.y + radius * 1.3,
            center.z + radius * 2.6
        )
        cameraNode.look(at: center)

        let key = SCNLight()
        key.type = .omni
        key.intensity = 1_050
        key.color = NSColor(calibratedWhite: 1.0, alpha: 1.0)
        let keyNode = SCNNode()
        keyNode.light = key
        keyNode.position = SCNVector3(center.x + radius * 1.8, center.y + radius * 2.1, center.z + radius * 2.2)

        let fill = SCNLight()
        fill.type = .ambient
        fill.intensity = 430
        fill.color = NSColor(calibratedRed: 0.52, green: 0.67, blue: 0.78, alpha: 1)
        let fillNode = SCNNode()
        fillNode.light = fill

        scene.rootNode.addChildNode(cameraNode)
        scene.rootNode.addChildNode(keyNode)
        scene.rootNode.addChildNode(fillNode)
        view.scene = scene
        view.pointOfView = cameraNode
        view.defaultCameraController.target = center
        coordinator.target = center
        coordinator.homeTransform = cameraNode.transform
    }

    private func resetCamera(in view: SCNView, coordinator: Coordinator, animated: Bool) {
        guard let camera = view.pointOfView, let transform = coordinator.homeTransform else {
            return
        }
        SCNTransaction.begin()
        SCNTransaction.animationDuration = animated ? 0.28 : 0
        camera.transform = transform
        SCNTransaction.commit()
        view.defaultCameraController.target = coordinator.target
    }
}
