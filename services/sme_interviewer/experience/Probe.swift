import Foundation
import PersonaPlex
import AudioCommon
import MLX

@main struct Probe {
    static func main() async throws {
        let args = CommandLine.arguments
        guard args.count == 4 else { fatalError("Usage: experience-probe MODEL_DIR INPUT_WAV OUTPUT_DIR") }
        let directory = URL(fileURLWithPath: args[1])
        let output = URL(fileURLWithPath: args[3])
        try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
        let loaded = CFAbsoluteTimeGetCurrent()
        let model = try await PersonaPlexModel.fromPretrained(modelId: PersonaPlexModel.modelId8bit,
            cacheDir: directory, offlineMode: true)
        print("Model load seconds: \(CFAbsoluteTimeGetCurrent() - loaded)")
        model.warmUp()
        let audio = try AudioFileLoader.load(url: URL(fileURLWithPath: args[2]), targetSampleRate: 24000)
        let prompt = model.tokenizeSystemPrompt("You are a patient British interviewer. Listen carefully. Ask one brief question about the user's example. Do not invent facts.")
        var measurements: [[String: Any]] = []
        for attempt in 0..<2 {
            let start = CFAbsoluteTimeGetCurrent()
            var samples: [Float] = []
            var arrival: [Double] = []
            var text = ""
            for try await chunk in model.respondStream(userAudio: audio, voice: .NATF1,
                systemPromptTokens: prompt, maxSteps: 100,
                streaming: .init(firstChunkFrames: 3, chunkFrames: 3), verbose: true) {
                arrival.append(CFAbsoluteTimeGetCurrent() - start)
                samples.append(contentsOf: chunk.samples)
                if chunk.isFinal { text = model.tokenizer?.decode(chunk.textTokens) ?? "" }
            }
            let elapsed = CFAbsoluteTimeGetCurrent() - start
            try WAVWriter.write(samples: samples, sampleRate: 24000, to: output.appendingPathComponent("response-\(attempt).wav"))
            measurements.append(["attempt": attempt, "first_chunk_seconds": arrival.first ?? -1,
                "total_seconds": elapsed, "audio_seconds": Double(samples.count) / 24000,
                "chunk_arrival_seconds": arrival, "text": text,
                "mode": "streamed response to prerecorded input, not live microphone duplex"])
            let data = try JSONSerialization.data(withJSONObject: measurements, options: [.prettyPrinted, .sortedKeys])
            try data.write(to: output.appendingPathComponent("measurements.json"))
            print(String(data: data, encoding: .utf8)!)
        }
        var liveResults: [[String: Any]] = []
        for attempt in 0..<2 {
            let frames = 200
            let ring = AudioRingBuffer(capacity: 24000 * 30)
            let start = CFAbsoluteTimeGetCurrent()
            let feeder = Task.detached {
                for frame in 0..<frames {
                    let deadline = start + Double(frame) * 0.08
                    let wait = deadline - CFAbsoluteTimeGetCurrent()
                    if wait > 0 { try await Task.sleep(nanoseconds: UInt64(wait * 1_000_000_000)) }
                    var samples = [Float](repeating: 0, count: 1920)
                    let offset = frame * 1920
                    if offset < audio.count {
                        for i in 0..<min(1920, audio.count - offset) { samples[i] = audio[offset + i] }
                    }
                    ring.write(samples)
                }
            }
            var arrivals: [Double] = []
            var backlog: [Int] = []
            var samples: [Float] = []
            for try await frame in model.respondRealtime(voice: .NATF1, systemPromptTokens: prompt,
                userAudioBuffer: ring, maxSteps: frames, verbose: true) {
                arrivals.append(CFAbsoluteTimeGetCurrent() - start)
                backlog.append(ring.available)
                samples.append(contentsOf: frame)
            }
            try await feeder.value
            try WAVWriter.write(samples: samples, sampleRate: 24000, to: output.appendingPathComponent("paced-\(attempt).wav"))
            liveResults.append(["attempt": attempt, "input_frame_count": frames, "frame_duration_ms": 80,
                "chunk_arrival_seconds": arrivals, "input_backlog_samples": backlog,
                "first_chunk_seconds": arrivals.first ?? -1, "total_seconds": CFAbsoluteTimeGetCurrent() - start,
                "audio_seconds": Double(samples.count) / 24000,
                "mode": "realtime inference with paced fictional WAV input; no microphone or speaker feedback"])
            try JSONSerialization.data(withJSONObject: liveResults, options: [.prettyPrinted, .sortedKeys])
                .write(to: output.appendingPathComponent("paced-measurements.json"))
            print("Paced attempt \(attempt): \(arrivals.count) frames, max queued input \(backlog.max() ?? 0) samples")
        }
    }
}
