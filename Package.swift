// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "FullSpectrumStudio",
    platforms: [
        .macOS(.v14)
    ],
    products: [
        .executable(name: "FullSpectrumStudio", targets: ["FullSpectrumStudio"])
    ],
    targets: [
        .executableTarget(
            name: "FullSpectrumStudio",
            path: "Sources/FullSpectrumStudio"
        )
    ]
)
