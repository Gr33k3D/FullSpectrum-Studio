import Foundation

enum DiagnosticPrivacy {
    static func safeMessage(_ message: String) -> String {
        let text = message.trimmingCharacters(in: .whitespacesAndNewlines)
        let lowered = text.lowercased()
        let markers = [
            NSHomeDirectory().lowercased(),
            "/users/",
            "/home/",
            "\\users\\",
            "remaininggrams",
            "\"spools\"",
            "catalogsource",
            ".3mf",
            ".obj",
            ".glb",
            ".json"
        ]
        let hasWindowsAbsolutePath = text.count > 2 && [":\\", ":/"].contains(String(text.dropFirst().prefix(2)))
        if hasWindowsAbsolutePath || markers.contains(where: { !$0.isEmpty && lowered.contains($0) }) {
            return "Conversion failed. Technical details are available in the private local log."
        }
        return String((text.isEmpty ? "Conversion failed." : text).prefix(800))
    }

    static func shareableErrorReport(message: String, logCreated: Bool) -> String {
        var lines = [
            "FullSpectrum Studio conversion error",
            "",
            "Conversion failed. Technical details are available in the private local log.",
            "",
            "The exception text, local paths, model names, inventory data, and raw engine output were excluded."
        ]
        if logCreated {
            lines.append("A detailed diagnostic log was saved locally and is not included here.")
        }
        return lines.joined(separator: "\n")
    }
}
