// Built-in pretrained Apple Vision tracker, not an avatar model trained by this lab.
import Foundation
import Vision
import ImageIO

let folder = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
let names = try FileManager.default.contentsOfDirectory(atPath: folder.path)
    .filter { $0.hasSuffix(".jpg") || $0.hasSuffix(".png") }.sorted()
func points(_ region: VNFaceLandmarkRegion2D?) -> [[Double]] {
    guard let region = region else { return [] }
    return region.normalizedPoints.map { [Double($0.x), Double($0.y)] }
}
var records: [[String: Any]] = []
for name in names {
    let request = VNDetectFaceLandmarksRequest()
    request.preferBackgroundProcessing = true
    do {
        try VNImageRequestHandler(url: folder.appendingPathComponent(name), options: [:]).perform([request])
        let faces = (request.results ?? []).map { face -> [String: Any] in
            let b = face.boundingBox
            return ["confidence": Double(face.confidence), "bbox": [Double(b.minX), Double(b.minY), Double(b.width), Double(b.height)],
                "outer_lips": points(face.landmarks?.outerLips), "inner_lips": points(face.landmarks?.innerLips),
                "left_eye": points(face.landmarks?.leftEye), "right_eye": points(face.landmarks?.rightEye)]
        }
        records.append(["frame": name, "faces": faces])
    } catch { records.append(["frame": name, "error": String(describing: error)]) }
}
let data = try JSONSerialization.data(withJSONObject: ["tracker": "Apple Vision VNDetectFaceLandmarksRequest", "revision": VNDetectFaceLandmarksRequest.defaultRevision, "records": records], options: [.sortedKeys])
FileHandle.standardOutput.write(data)
