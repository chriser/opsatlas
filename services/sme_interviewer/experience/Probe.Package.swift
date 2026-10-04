// swift-tools-version: 5.10
import PackageDescription
let package = Package(name: "ExperienceProbe", platforms: [.macOS("15.0")],
    products: [.executable(name: "experience-probe", targets: ["ExperienceProbe"])],
    dependencies: [
        .package(url: "https://github.com/ml-explore/mlx-swift", from: "0.30.0"),
        .package(url: "https://github.com/huggingface/swift-transformers", from: "1.1.6")
    ],
    targets: [
        .target(name: "AudioCommon", dependencies: [.product(name: "Hub", package: "swift-transformers")]),
        .target(name: "MLXCommon", dependencies: ["AudioCommon", .product(name: "MLX", package: "mlx-swift"),
            .product(name: "MLXNN", package: "mlx-swift"), .product(name: "MLXFast", package: "mlx-swift"),
            .product(name: "MLXFFT", package: "mlx-swift")]),
        .target(name: "PersonaPlex", dependencies: ["AudioCommon", "MLXCommon", .product(name: "MLX", package: "mlx-swift"),
            .product(name: "MLXNN", package: "mlx-swift"), .product(name: "MLXFast", package: "mlx-swift")]),
        .executableTarget(name: "ExperienceProbe", dependencies: ["PersonaPlex", "AudioCommon", .product(name: "MLX", package: "mlx-swift")])
    ])
