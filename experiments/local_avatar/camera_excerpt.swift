// SDR camera playback for validation timing review; no fitting or test input.
import Foundation
import AVFoundation
import CoreGraphics

guard CommandLine.arguments.count == 5 else { fatalError("Usage: camera_excerpt source output start duration") }
let source = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2])
let start = Double(CommandLine.arguments[3])!
let duration = Double(CommandLine.arguments[4])!
guard start.isFinite && start >= 0 && duration.isFinite && duration > 0 && duration <= 30 else {
    fatalError("Invalid excerpt bounds")
}
guard !FileManager.default.fileExists(atPath: output.path) else { fatalError("Excerpt already exists") }
let generator = AVAssetImageGenerator(asset: AVURLAsset(url: source))
generator.appliesPreferredTrackTransform = true
generator.maximumSize = CGSize(width: 576, height: 1024)
generator.dynamicRangePolicy = .forceSDR
generator.requestedTimeToleranceBefore = CMTime(seconds: 1.0 / 60, preferredTimescale: 60000)
generator.requestedTimeToleranceAfter = generator.requestedTimeToleranceBefore
let pipe = Pipe()
let encoder = Process()
encoder.executableURL = URL(fileURLWithPath: "/opt/homebrew/bin/ffmpeg")
encoder.arguments = ["-v", "error", "-f", "rawvideo", "-pixel_format", "rgba", "-video_size", "576x1024",
                     "-framerate", "30", "-i", "pipe:0", "-an", "-c:v", "libx264", "-threads", "2",
                     "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", output.path]
encoder.standardInput = pipe
encoder.standardOutput = FileHandle.nullDevice
try encoder.run()
var times: [[String: Double]] = []
for index in 0..<Int((duration * 30).rounded()) {
    let requested = start + Double(index) / 30
    let time = CMTime(seconds: requested, preferredTimescale: 60000)
    var frame: (image: CGImage, actualTime: CMTime)?
    for _ in 0..<3 {
        do { frame = try await generator.image(at: time); break } catch { continue }
    }
    guard let frame = frame else { fatalError("Camera excerpt request failed") }
    var data = Data(count: 576 * 1024 * 4)
    data.withUnsafeMutableBytes { bytes in
        let context = CGContext(data: bytes.baseAddress, width: 576, height: 1024, bitsPerComponent: 8,
                                bytesPerRow: 576 * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue | CGBitmapInfo.byteOrder32Big.rawValue)!
        context.draw(frame.image, in: CGRect(x: 0, y: 0, width: 576, height: 1024))
    }
    try pipe.fileHandleForWriting.write(contentsOf: data)
    times.append(["requested_seconds": requested, "source_seconds": CMTimeGetSeconds(frame.actualTime)])
}
try pipe.fileHandleForWriting.close()
encoder.waitUntilExit()
guard encoder.terminationStatus == 0 else { fatalError("Excerpt encoder failed") }
let json = try JSONSerialization.data(withJSONObject: times, options: [.sortedKeys])
try json.write(to: output.deletingPathExtension().appendingPathExtension("times.json"))
print("Private SDR camera excerpt encoded.")
