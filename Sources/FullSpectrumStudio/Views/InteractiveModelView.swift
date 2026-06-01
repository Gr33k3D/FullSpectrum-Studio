import AppKit
import SceneKit
import SwiftUI

struct InteractiveModelView: NSViewRepresentable {
    let meshURL: URL
    let resetToken: Int
    let wireframe: Bool
    let performance: ViewerPerformance
    let displayScale: Double

    final class Coordinator {
        var meshURL: URL?
        var resetToken = -1
        var wireframe = false
        var displayScale = 1.0
        var homeTransform: SCNMatrix4?
        var target = SCNVector3Zero
        var contentRoot: SCNNode?
        var floorNode: SCNNode?
        var baseRadius: CGFloat = 1
        var baseBottomY: CGFloat = -1
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
        view.defaultCameraController.interactionMode = .orbitTurntable
        view.autoenablesDefaultLighting = false
        view.antialiasingMode = .multisampling4X
        view.preferredFramesPerSecond = 60
        view.rendersContinuously = false
        return view
    }

    func updateNSView(_ view: SCNView, context: Context) {
        if context.coordinator.meshURL != meshURL {
            loadScene(in: view, coordinator: context.coordinator)
            context.coordinator.meshURL = meshURL
        }
        switch performance {
        case .fast:
            view.preferredFramesPerSecond = 24
            view.antialiasingMode = .none
        case .balanced:
            view.preferredFramesPerSecond = 30
            view.antialiasingMode = .multisampling2X
        case .high:
            view.preferredFramesPerSecond = 45
            view.antialiasingMode = .multisampling4X
        case .maximum:
            view.preferredFramesPerSecond = 60
            view.antialiasingMode = .multisampling4X
        }
        if context.coordinator.wireframe != wireframe {
            context.coordinator.contentRoot?.enumerateChildNodes { node, _ in
                node.geometry?.materials.forEach { material in
                    material.fillMode = wireframe ? .lines : .fill
                }
            }
            context.coordinator.wireframe = wireframe
        }
        if abs(context.coordinator.displayScale - displayScale) > 0.001 {
            applyDisplayScale(in: view, coordinator: context.coordinator, animated: true)
        }
        if context.coordinator.resetToken != resetToken {
            resetCamera(in: view, coordinator: context.coordinator, animated: true)
            context.coordinator.resetToken = resetToken
        }
    }

    private func loadScene(in view: SCNView, coordinator: Coordinator) {
        guard let loadedScene = try? SCNScene(url: meshURL, options: nil) else {
            return
        }
        let scene = SCNScene()
        scene.background.contents = NSColor.clear
        let contentRoot = SCNNode()
        contentRoot.name = "preview-content"
        for child in loadedScene.rootNode.childNodes {
            child.removeFromParentNode()
            contentRoot.addChildNode(child)
        }
        contentRoot.enumerateChildNodes { node, _ in
            node.geometry?.materials.forEach { material in
                material.lightingModel = .physicallyBased
                material.roughness.contents = 0.72
                material.metalness.contents = 0.0
                material.emission.intensity = 0.06
                material.isDoubleSided = true
                material.fillMode = wireframe ? .lines : .fill
            }
        }

        let (minimum, maximum) = contentRoot.boundingBox
        let center = SCNVector3(
            (minimum.x + maximum.x) / 2,
            (minimum.y + maximum.y) / 2,
            (minimum.z + maximum.z) / 2
        )
        let span = max(maximum.x - minimum.x, max(maximum.y - minimum.y, maximum.z - minimum.z))
        let radius = max(span / 2, 1)
        contentRoot.pivot = SCNMatrix4MakeTranslation(center.x, center.y, center.z)
        scene.rootNode.addChildNode(contentRoot)

        let cameraNode = SCNNode()
        let camera = SCNCamera()
        camera.fieldOfView = 38
        camera.zNear = Double(max(radius * 0.002, 0.01))
        camera.zFar = Double(radius * 40)
        cameraNode.camera = camera
        cameraNode.position = homeCameraPosition(radius: radius * clampedDisplayScale)
        cameraNode.look(at: SCNVector3Zero)

        let key = SCNLight()
        key.type = .directional
        key.intensity = 1_150
        key.color = NSColor(calibratedWhite: 1.0, alpha: 1.0)
        key.castsShadow = true
        key.shadowRadius = 5
        key.shadowSampleCount = 12
        let keyNode = SCNNode()
        keyNode.light = key
        keyNode.position = SCNVector3(radius * 1.6, radius * 2.4, radius * 2.0)
        keyNode.look(at: SCNVector3Zero)

        let fill = SCNLight()
        fill.type = .ambient
        fill.intensity = 520
        fill.color = NSColor(calibratedRed: 0.55, green: 0.68, blue: 0.76, alpha: 1)
        let fillNode = SCNNode()
        fillNode.light = fill

        let rim = SCNLight()
        rim.type = .omni
        rim.intensity = 320
        rim.color = NSColor(calibratedRed: 0.45, green: 0.9, blue: 1.0, alpha: 1)
        let rimNode = SCNNode()
        rimNode.light = rim
        rimNode.position = SCNVector3(-radius * 1.7, radius * 0.9, -radius * 1.9)

        let floorNode = makeFloorNode(radius: radius, bottomY: minimum.y - center.y)
        scene.rootNode.addChildNode(floorNode)
        scene.rootNode.addChildNode(cameraNode)
        scene.rootNode.addChildNode(keyNode)
        scene.rootNode.addChildNode(fillNode)
        scene.rootNode.addChildNode(rimNode)
        view.scene = scene
        view.pointOfView = cameraNode
        view.defaultCameraController.target = SCNVector3Zero
        coordinator.target = SCNVector3Zero
        coordinator.homeTransform = cameraNode.transform
        coordinator.resetToken = resetToken
        coordinator.wireframe = wireframe
        coordinator.displayScale = displayScale
        coordinator.contentRoot = contentRoot
        coordinator.floorNode = floorNode
        coordinator.baseRadius = radius
        coordinator.baseBottomY = minimum.y - center.y
        applyDisplayScale(in: view, coordinator: coordinator, animated: false)
    }

    private var clampedDisplayScale: CGFloat {
        CGFloat(max(0.35, min(1.0, displayScale)))
    }

    private func applyDisplayScale(in view: SCNView, coordinator: Coordinator, animated: Bool) {
        let scale = clampedDisplayScale
        SCNTransaction.begin()
        SCNTransaction.animationDuration = animated ? 0.2 : 0
        coordinator.contentRoot?.scale = SCNVector3(scale, scale, scale)
        coordinator.floorNode?.position.y = coordinator.baseBottomY * scale - max(coordinator.baseRadius * 0.025, 0.02)
        if let camera = view.pointOfView {
            camera.position = homeCameraPosition(radius: coordinator.baseRadius * scale)
            camera.look(at: coordinator.target)
            coordinator.homeTransform = camera.transform
        }
        SCNTransaction.commit()
        view.defaultCameraController.target = coordinator.target
        coordinator.displayScale = displayScale
    }

    private func homeCameraPosition(radius: CGFloat) -> SCNVector3 {
        SCNVector3(radius * 1.75, radius * 1.25, radius * 2.35)
    }

    private func makeFloorNode(radius: CGFloat, bottomY: CGFloat) -> SCNNode {
        let h2cPlateWidth: CGFloat = 330
        let h2cPlateDepth: CGFloat = 320
        let modelSpan = radius * 2
        let plateScale = modelSpan < 5
            ? max(radius * 4.2, 2) / h2cPlateWidth
            : max(1, (modelSpan * 1.12) / h2cPlateWidth)
        let floor = SCNPlane(width: h2cPlateWidth * plateScale, height: h2cPlateDepth * plateScale)
        let material = SCNMaterial()
        material.diffuse.contents = h2cPlateTexture()
        material.lightingModel = .constant
        material.isDoubleSided = true
        material.transparency = 0.82
        floor.materials = [material]
        let node = SCNNode(geometry: floor)
        node.name = "h2c-textured-pei-plate"
        node.eulerAngles.x = -.pi / 2
        node.position = SCNVector3(0, bottomY - max(radius * 0.025, 0.02), 0)
        return node
    }

    private func h2cPlateTexture() -> NSImage {
        let size = NSSize(width: 528, height: 512)
        let image = NSImage(size: size)
        image.lockFocus()
        NSColor(calibratedRed: 0.075, green: 0.085, blue: 0.085, alpha: 1).setFill()
        NSRect(origin: .zero, size: size).fill()
        NSColor(calibratedRed: 0.16, green: 0.18, blue: 0.18, alpha: 1).setFill()
        NSBezierPath(roundedRect: NSRect(x: 12, y: 12, width: 504, height: 488), xRadius: 18, yRadius: 18).fill()

        for index in stride(from: 32, through: 496, by: 16) {
            let alpha: CGFloat = index % 80 == 0 ? 0.28 : 0.11
            NSColor(calibratedRed: 0.55, green: 0.64, blue: 0.68, alpha: alpha).setStroke()
            let vertical = NSBezierPath()
            vertical.move(to: NSPoint(x: index, y: 22))
            vertical.line(to: NSPoint(x: index, y: 490))
            vertical.lineWidth = index % 80 == 0 ? 1.3 : 0.65
            vertical.stroke()
        }
        for index in stride(from: 32, through: 480, by: 16) {
            let alpha: CGFloat = index % 80 == 0 ? 0.28 : 0.11
            NSColor(calibratedRed: 0.55, green: 0.64, blue: 0.68, alpha: alpha).setStroke()
            let horizontal = NSBezierPath()
            horizontal.move(to: NSPoint(x: 22, y: index))
            horizontal.line(to: NSPoint(x: 506, y: index))
            horizontal.lineWidth = index % 80 == 0 ? 1.3 : 0.65
            horizontal.stroke()
        }

        NSColor(calibratedRed: 0.18, green: 0.78, blue: 0.96, alpha: 0.9).setStroke()
        let border = NSBezierPath(roundedRect: NSRect(x: 15, y: 15, width: 498, height: 482), xRadius: 16, yRadius: 16)
        border.lineWidth = 2.2
        border.stroke()

        let center = NSPoint(x: size.width / 2, y: size.height / 2)
        let centerMark = NSBezierPath()
        centerMark.move(to: NSPoint(x: center.x - 28, y: center.y))
        centerMark.line(to: NSPoint(x: center.x + 28, y: center.y))
        centerMark.move(to: NSPoint(x: center.x, y: center.y - 28))
        centerMark.line(to: NSPoint(x: center.x, y: center.y + 28))
        centerMark.lineWidth = 1.8
        centerMark.stroke()

        let attrs: [NSAttributedString.Key: Any] = [
            .font: NSFont.monospacedSystemFont(ofSize: 22, weight: .semibold),
            .foregroundColor: NSColor(calibratedRed: 0.72, green: 0.88, blue: 0.94, alpha: 0.9)
        ]
        "H2C 330 x 320 Textured PEI".draw(at: NSPoint(x: 28, y: 464), withAttributes: attrs)
        "FRONT".draw(at: NSPoint(x: 234, y: 30), withAttributes: attrs)
        image.unlockFocus()
        return image
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
