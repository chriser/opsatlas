// Private camera labels only. Apple Vision is reused, not trained by this lab.
import Foundation
import AVFoundation
import Vision
import ImageIO
import UniformTypeIdentifiers

guard CommandLine.arguments.count == 5 else {
    fatalError("Usage: track_camera source output duration fps")
}
let source = URL(fileURLWithPath: CommandLine.arguments[1])
let folder = URL(fileURLWithPath: CommandLine.arguments[2], isDirectory: true)
let duration = Double(CommandLine.arguments[3])!
let fps = Double(CommandLine.arguments[4])!
guard duration.isFinite && duration > 0 && fps == 30 else { fatalError("Invalid capture settings") }
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
let destination = folder.appendingPathComponent("landmarks.jsonl")
guard !FileManager.default.fileExists(atPath: destination.path) else { fatalError("Labels already exist") }
FileManager.default.createFile(atPath: destination.path, contents: nil)
let output = try FileHandle(forWritingTo: destination)
let generator = AVAssetImageGenerator(asset: AVURLAsset(url: source))
generator.appliesPreferredTrackTransform = true
generator.maximumSize = CGSize(width: 640, height: 1138)
generator.dynamicRangePolicy = .forceSDR
generator.requestedTimeToleranceBefore = CMTime(seconds: 0.5 / fps, preferredTimescale: 60000)
generator.requestedTimeToleranceAfter = generator.requestedTimeToleranceBefore
let count = Int(ceil(duration * fps))
func points(_ region: VNFaceLandmarkRegion2D?) -> [[Double]] {
    guard let region = region else { return [] }
    return region.normalizedPoints.map { [Double($0.x), Double($0.y)] }
}
func inspect(_ image: CGImage) throws -> [[String: Any]] {
    let request = VNDetectFaceLandmarksRequest()
    request.revision = 3
    request.preferBackgroundProcessing = true
    try VNImageRequestHandler(cgImage: image, options: [:]).perform([request])
    return (request.results ?? []).map { face in
        let b = face.boundingBox
        return ["confidence": Double(face.confidence),
                "bbox": [Double(b.minX), Double(b.minY), Double(b.width), Double(b.height)],
                "outer_lips": points(face.landmarks?.outerLips), "inner_lips": points(face.landmarks?.innerLips),
                "left_eye": points(face.landmarks?.leftEye), "right_eye": points(face.landmarks?.rightEye)]
    }
}
func label(_ image: CGImage, _ actual: CMTime, _ index: Int, _ requested: Double) throws -> [String: Any] {
    let faces = try autoreleasepool { try inspect(image) }
    // QC stills are allowed only for training/validation directories.
    if folder.lastPathComponent != "C" && index % 900 == 0 {
        let url = folder.appendingPathComponent(String(format: "qc-%06d.png", index))
        let png = CGImageDestinationCreateWithURL(url as CFURL, UTType.png.identifier as CFString, 1, nil)!
        CGImageDestinationAddImage(png, image, nil)
        guard CGImageDestinationFinalize(png) else { fatalError("QC still write failed") }
    }
    return ["index": index, "requested_seconds": requested, "source_seconds": CMTimeGetSeconds(actual),
            "width": image.width, "height": image.height, "faces": faces]
}
// Bounded ten-second batches; retain coordinates, not thousands of RGB frames.
for start in stride(from: 0, to: count, by: 300) {
    let times = (start..<min(start + 300, count)).map {
        CMTime(seconds: Double($0) / fps, preferredTimescale: 60000)
    }
    var records: [Int: [String: Any]] = [:]
    var failures: [(Int, CMTime)] = []
    for await result in generator.images(for: times) {
        let requested = CMTimeGetSeconds(result.requestedTime)
        let index = Int((requested * fps).rounded())
        var record: [String: Any] = ["index": index, "requested_seconds": requested]
        do {
            record = try label(result.image, result.actualTime, index, requested)
        } catch {
            record["error"] = String(describing: error)
            failures.append((index, result.requestedTime))
        }
        records[index] = record
    }
    // Some HEVC thumbnail requests fail transiently; retry after the batch drains.
    for (index, time) in failures {
        for attempt in 1...2 {
            do {
                let frame = try await generator.image(at: time)
                var record = try label(frame.image, frame.actualTime, index, CMTimeGetSeconds(time))
                record["retries"] = attempt
                records[index] = record
                break
            } catch {
                records[index]?["error"] = String(describing: error)
                records[index]?["retries"] = attempt
            }
        }
    }
    for index in records.keys.sorted() {
        var data = try JSONSerialization.data(withJSONObject: records[index]!, options: [.sortedKeys])
        data.append(10)
        try output.write(contentsOf: data)
    }
    print("Labelled requests \(min(start + 300, count))/\(count)")
    fflush(stdout)
}
try output.close()
