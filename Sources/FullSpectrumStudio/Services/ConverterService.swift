import Foundation

enum ConverterError: LocalizedError {
    case engineMissing
    case processFailure(message: String, debugReport: String, logURL: URL?)

    var errorDescription: String? {
        switch self {
        case .engineMissing:
            return "The conversion engine is missing from the application bundle."
        case .processFailure(let message, _, _):
            return message
        }
    }

    var debugReport: String? {
        switch self {
        case .engineMissing:
            return nil
        case .processFailure(_, let debugReport, _):
            return debugReport
        }
    }

    var logURL: URL? {
        switch self {
        case .engineMissing:
            return nil
        case .processFailure(_, _, let logURL):
            return logURL
        }
    }
}

private final class ProcessDiagnostics: @unchecked Sendable {
    private var data = Data()
    private var lineBuffer = Data()
    private let lock = NSLock()

    func consume(_ chunk: Data, decodeProgress: Bool = false) -> [ConversionProgress] {
        lock.lock()
        defer { lock.unlock() }
        data.append(chunk)
        guard decodeProgress else { return [] }
        lineBuffer.append(chunk)
        var events: [ConversionProgress] = []
        while let newline = lineBuffer.firstIndex(of: 0x0A) {
            let line = Data(lineBuffer[..<newline])
            lineBuffer.removeSubrange(...newline)
            if let event = try? JSONDecoder().decode(ConversionProgress.self, from: line) {
                events.append(event)
            }
        }
        return events
    }

    func snapshot() -> Data {
        lock.lock()
        defer { lock.unlock() }
        return data
    }
}

struct ConverterService {
    func inventory() async throws -> InventorySnapshot {
        try await execute(
            arguments: ["--inventory", "--json"],
            type: InventorySnapshot.self
        )
    }

    func metadata(
        file: URL,
        thumbnailURL: URL
    ) async throws -> ProjectInspection {
        try await execute(
            arguments: [
                "--inspect", "--json",
                "--metadata-only",
                "--thumbnail-out", thumbnailURL.path,
                file.path
            ],
            type: ProjectInspection.self
        )
    }

    func previewMesh(
        file: URL,
        outputURL: URL,
        mixPrediction: MixPrediction = .bambu,
        textureOverride: URL? = nil,
        progress: (@Sendable (Double, String) -> Void)? = nil
    ) async throws -> ProjectInspection {
        var arguments = [
                "--inspect", "--json",
                "--preview-mesh-out", outputURL.path,
                "--mix-model", mixPrediction.rawValue,
                file.path
            ]
        if let textureOverride {
            arguments.insert(contentsOf: ["--texture", textureOverride.path], at: arguments.count - 1)
        }
        return try await execute(
            arguments: arguments,
            type: ProjectInspection.self,
            progress: progress
        )
    }

    func convert(
        file: URL,
        mode: PaletteMode,
        paletteSource: PaletteSource,
        realSlots: RealSlotSelection,
        reference: URL?,
        customPalette: URL?,
        textureOverride: URL?,
        qualityBias: String,
        catalogRegion: CatalogRegion,
        mixPrediction: MixPrediction,
        outputDirectory: URL,
        progress: @escaping @Sendable (Double, String) -> Void
    ) async throws -> ConversionResult {
        let analysisDirectory = FileManager.default.temporaryDirectory
            .appendingPathComponent("FullSpectrum-Analysis-\(UUID().uuidString)", isDirectory: true)
        var arguments = [
                "--json",
                "--mode", mode.rawValue,
                "--palette-source", paletteSource.rawValue,
                "--real-slots", realSlots.rawValue,
                "--quality-bias", qualityBias,
                "--catalog-region", catalogRegion.rawValue,
                "--mix-model", mixPrediction.rawValue,
                "--analysis-dir", analysisDirectory.path,
                "--output-dir", outputDirectory.path,
                "--no-reveal",
                file.path
            ]
        if let reference {
            arguments.insert(contentsOf: ["--reference", reference.path], at: arguments.count - 1)
        }
        if let customPalette {
            arguments.insert(contentsOf: ["--custom-palette", customPalette.path], at: arguments.count - 1)
        }
        if let textureOverride {
            arguments.insert(contentsOf: ["--texture", textureOverride.path], at: arguments.count - 1)
        }
        return try await execute(
            arguments: arguments,
            type: ConversionResult.self,
            progress: progress
        )
    }

    private struct DecodedOutput<T> {
        let value: T
        let sourceDescription: String
    }

    private func execute<T: Decodable>(
        arguments: [String],
        type: T.Type,
        progress: (@Sendable (Double, String) -> Void)? = nil
    ) async throws -> T {
        let task = Task.detached(priority: .userInitiated) {
            guard let engine = Bundle.main.url(forResource: "FullSpectrumEngine", withExtension: "py") else {
                throw ConverterError.engineMissing
            }

            let process = Process()
            process.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
            process.arguments = [engine.path] + arguments
            let stdout = Pipe()
            let stderr = Pipe()
            process.standardOutput = stdout
            process.standardError = stderr

            let stdoutDiagnostics = ProcessDiagnostics()
            let stderrDiagnostics = ProcessDiagnostics()
            stdout.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                guard !data.isEmpty else { return }
                _ = stdoutDiagnostics.consume(data)
            }
            stderr.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                guard !data.isEmpty else { return }
                let events = stderrDiagnostics.consume(data, decodeProgress: true)
                events.forEach { progress?($0.progress, $0.message) }
            }

            try Task.checkCancellation()
            try process.run()
            while process.isRunning {
                if Task.isCancelled {
                    await Self.terminate(process)
                    throw CancellationError()
                }
                try await Task.sleep(nanoseconds: 50_000_000)
            }
            stdout.fileHandleForReading.readabilityHandler = nil
            stderr.fileHandleForReading.readabilityHandler = nil

            let remainingOutputData = stdout.fileHandleForReading.readDataToEndOfFile()
            let remainingErrorData = stderr.fileHandleForReading.readDataToEndOfFile()
            _ = stdoutDiagnostics.consume(remainingOutputData)
            stderrDiagnostics.consume(remainingErrorData, decodeProgress: true).forEach { progress?($0.progress, $0.message) }
            let outputData = stdoutDiagnostics.snapshot()
            let diagnosticsData = stderrDiagnostics.snapshot()

            if process.terminationStatus != 0 {
                let message = Self.failureMessage(
                    stdout: outputData,
                    stderr: diagnosticsData,
                    fallback: "Conversion failed with exit code \(process.terminationStatus)."
                )
                let logURL = Self.writeDebugLog(
                    arguments: arguments,
                    terminationStatus: process.terminationStatus,
                    stdout: outputData,
                    stderr: diagnosticsData,
                    decodeError: nil
                )
                throw ConverterError.processFailure(
                    message: message,
                    debugReport: Self.debugReport(message: message, logURL: logURL, stdout: outputData, stderr: diagnosticsData),
                    logURL: logURL
                )
            }

            do {
                return try Self.decodeJSONOutput(type, from: outputData).value
            } catch {
                let message = Self.decodeFailureMessage(error: error, stdout: outputData, stderr: diagnosticsData)
                let logURL = Self.writeDebugLog(
                    arguments: arguments,
                    terminationStatus: process.terminationStatus,
                    stdout: outputData,
                    stderr: diagnosticsData,
                    decodeError: error
                )
                throw ConverterError.processFailure(
                    message: message,
                    debugReport: Self.debugReport(message: message, logURL: logURL, stdout: outputData, stderr: diagnosticsData),
                    logURL: logURL
                )
            }
        }
        return try await withTaskCancellationHandler {
            try await task.value
        } onCancel: {
            task.cancel()
        }
    }

    private static func decodeJSONOutput<T: Decodable>(_ type: T.Type, from data: Data) throws -> DecodedOutput<T> {
        let trimmed = trimWhitespace(data)
        do {
            return DecodedOutput(value: try JSONDecoder().decode(type, from: trimmed), sourceDescription: "complete stdout")
        } catch {
            let text = String(data: data, encoding: .utf8) ?? ""
            let lines = text.split(whereSeparator: \.isNewline).map(String.init).filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
            for line in lines.reversed() {
                let candidate = Data(line.utf8)
                if let decoded = try? JSONDecoder().decode(type, from: candidate) {
                    return DecodedOutput(value: decoded, sourceDescription: "last JSON line")
                }
            }
            throw error
        }
    }

    private static func trimWhitespace(_ data: Data) -> Data {
        guard let text = String(data: data, encoding: .utf8) else { return data }
        return Data(text.trimmingCharacters(in: .whitespacesAndNewlines).utf8)
    }

    private static func failureMessage(stdout: Data, stderr: Data, fallback: String) -> String {
        let stderrText = text(stderr)
        let stdoutText = text(stdout)
        let lines = significantLines(stderrText) + significantLines(stdoutText)
        if let explicit = lines.reversed().first(where: { $0.hasPrefix("ERROR:") }) {
            let message = explicit.dropFirst("ERROR:".count).trimmingCharacters(in: .whitespacesAndNewlines)
            if !message.isEmpty, message.lowercased() != "none" { return message }
        }
        if let exception = lines.reversed().first(where: { line in
            line.range(of: #"^[A-Za-z_][A-Za-z0-9_]*(Error|Exception):"#, options: .regularExpression) != nil
        }) {
            return exception
        }
        if let last = lines.reversed().first, last.lowercased() != "none" {
            return last
        }
        return fallback
    }

    private static func decodeFailureMessage(error: Error, stdout: Data, stderr: Data) -> String {
        let stdoutText = text(stdout)
        let stderrText = text(stderr)
        var pieces = [
            "The conversion engine finished, but the app could not read its JSON result.",
            "Decoder: \(error.localizedDescription)."
        ]
        if !stdoutText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            pieces.append("Stdout tail: \(tail(stdoutText, maxCharacters: 600))")
        }
        if !stderrText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
            pieces.append("Engine log tail: \(tail(stderrText, maxCharacters: 600))")
        }
        return pieces.joined(separator: "\n")
    }

    private static func debugReport(message: String, logURL: URL?, stdout: Data, stderr: Data) -> String {
        [
            "FullSpectrum Studio conversion error",
            "",
            message,
            "",
            logURL.map { "Debug log: \($0.path)" } ?? "Debug log: unavailable",
            "",
            "Engine stderr tail:",
            tail(text(stderr), maxCharacters: 2_400),
            "",
            "Engine stdout tail:",
            tail(text(stdout), maxCharacters: 2_400)
        ].joined(separator: "\n")
    }

    private static func writeDebugLog(arguments: [String], terminationStatus: Int32, stdout: Data, stderr: Data, decodeError: Error?) -> URL? {
        do {
            let root = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask).first!
                .appendingPathComponent("Logs", isDirectory: true)
                .appendingPathComponent("FullSpectrumStudio", isDirectory: true)
            try FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
            let formatter = DateFormatter()
            formatter.dateFormat = "yyyyMMdd-HHmmss"
            let url = root.appendingPathComponent("conversion-\(formatter.string(from: Date())).log")
            let body = [
                "FullSpectrum Studio conversion debug log",
                "Created: \(ISO8601DateFormatter().string(from: Date()))",
                "Command: /usr/bin/python3 FullSpectrumEngine.py \(arguments.map(shellQuoted).joined(separator: " "))",
                "Termination status: \(terminationStatus)",
                decodeError.map { "Decode error: \($0.localizedDescription)" } ?? nil,
                "",
                "===== STDERR =====",
                text(stderr),
                "",
                "===== STDOUT =====",
                text(stdout)
            ].compactMap { $0 }.joined(separator: "\n")
            try body.write(to: url, atomically: true, encoding: .utf8)
            return url
        } catch {
            return nil
        }
    }

    private static func significantLines(_ text: String) -> [String] {
        text.split(whereSeparator: \.isNewline)
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { line in
                guard !line.isEmpty else { return false }
                if line.hasPrefix("{"),
                   let data = line.data(using: .utf8),
                   let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                   object["progress"] != nil {
                    return false
                }
                return true
            }
    }

    private static func text(_ data: Data) -> String {
        String(data: data, encoding: .utf8) ?? "<\(data.count) non-UTF8 bytes>"
    }

    private static func tail(_ text: String, maxCharacters: Int) -> String {
        guard text.count > maxCharacters else { return text.trimmingCharacters(in: .whitespacesAndNewlines) }
        return "..." + text.suffix(maxCharacters)
    }

    private static func shellQuoted(_ value: String) -> String {
        "'\(value.replacingOccurrences(of: "'", with: "'\\''"))'"
    }

    private static func terminate(_ process: Process) async {
        guard process.isRunning else { return }
        process.terminate()
        for _ in 0..<20 {
            if !process.isRunning { return }
            try? await Task.sleep(nanoseconds: 100_000_000)
        }
        guard process.isRunning else { return }
        let killer = Process()
        killer.executableURL = URL(fileURLWithPath: "/bin/kill")
        killer.arguments = ["-KILL", "\(process.processIdentifier)"]
        try? killer.run()
        killer.waitUntilExit()
    }
}
