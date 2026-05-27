import Foundation

enum ConverterError: LocalizedError {
    case engineMissing
    case processFailure(String)

    var errorDescription: String? {
        switch self {
        case .engineMissing:
            return "The conversion engine is missing from the application bundle."
        case .processFailure(let message):
            return message
        }
    }
}

private final class ProcessDiagnostics: @unchecked Sendable {
    private var data = Data()
    private var lineBuffer = Data()
    private let lock = NSLock()

    func consume(_ chunk: Data) -> [ConversionProgress] {
        lock.lock()
        defer { lock.unlock() }
        data.append(chunk)
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

    func inspect(
        file: URL,
        thumbnailURL: URL,
        previewMeshURL: URL,
        textureOverride: URL? = nil,
        progress: @escaping @Sendable (Double, String) -> Void
    ) async throws -> ProjectInspection {
        var arguments = [
                "--inspect", "--json",
                "--thumbnail-out", thumbnailURL.path,
                "--preview-mesh-out", previewMeshURL.path,
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

    func previewMesh(file: URL, outputURL: URL, mixPrediction: MixPrediction = .perceptual, textureOverride: URL? = nil) async throws -> ProjectInspection {
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
            type: ProjectInspection.self
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
        qualityBias: Int,
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
                "--quality-bias", String(qualityBias),
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

            let diagnostics = ProcessDiagnostics()
            stderr.fileHandleForReading.readabilityHandler = { handle in
                let data = handle.availableData
                guard !data.isEmpty else { return }
                let events = diagnostics.consume(data)
                events.forEach { progress?($0.progress, $0.message) }
            }

            try Task.checkCancellation()
            try process.run()
            while process.isRunning {
                if Task.isCancelled {
                    process.terminate()
                    throw CancellationError()
                }
                try await Task.sleep(nanoseconds: 50_000_000)
            }
            stderr.fileHandleForReading.readabilityHandler = nil

            let outputData = stdout.fileHandleForReading.readDataToEndOfFile()
            let remainingErrorData = stderr.fileHandleForReading.readDataToEndOfFile()
            diagnostics.consume(remainingErrorData).forEach { progress?($0.progress, $0.message) }
            let diagnosticsData = diagnostics.snapshot()
            if process.terminationStatus != 0 {
                let details = String(data: diagnosticsData, encoding: .utf8)?
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                throw ConverterError.processFailure(details ?? "Conversion failed.")
            }

            do {
                return try JSONDecoder().decode(type, from: outputData)
            } catch {
                let diagnostics = String(data: diagnosticsData, encoding: .utf8) ?? ""
                throw ConverterError.processFailure("Could not read converter output. \(diagnostics)")
            }
        }
        return try await withTaskCancellationHandler {
            try await task.value
        } onCancel: {
            task.cancel()
        }
    }
}
