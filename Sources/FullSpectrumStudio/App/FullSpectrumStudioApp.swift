import AppKit
import SwiftUI

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
    }
}

@main
struct FullSpectrumStudioApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var store = StudioStore()

    var body: some Scene {
        WindowGroup("FullSpectrum Studio", id: "main") {
            ContentView()
                .environmentObject(store)
                .frame(minWidth: 820, minHeight: 640)
        }
        .defaultSize(width: 1240, height: 790)
        .commands {
            CommandGroup(replacing: .newItem) {
                Button("Open Painted 3MF or Textured OBJ/GLB...") {
                    store.chooseSourceFile()
                }
                .keyboardShortcut("o")
            }
            CommandMenu("Conversion") {
                Button("Convert Project") {
                    store.convert()
                }
                .keyboardShortcut("r")
                .disabled(store.selectedFile == nil || store.isWorking)

                Button("Reveal Output") {
                    store.revealOutput()
                }
                .disabled(store.result == nil)
            }
        }
    }
}
