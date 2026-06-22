// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "Herdi",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "Herdi",
            path: "Sources"
        )
    ]
)
