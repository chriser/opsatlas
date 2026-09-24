// Resident whisper.cpp/Silero adapter. PCM float32 pipe input; JSON-line output.
// No sockets, file uploads, or transcript logging. Linked against the pinned local whisper.cpp.
#include "whisper.h"
#include <iostream>
#include <vector>
#include <string>
#include <cmath>
#include <iomanip>

static void escaped(const std::string &text) {
    std::cout << '"';
    for (unsigned char c : text) {
        if (c == '"' || c == '\\') std::cout << '\\' << c;
        else if (c < 32) std::cout << "\\u" << std::hex << std::setw(4) << std::setfill('0') << int(c) << std::dec;
        else std::cout << c;
    }
    std::cout << '"';
}
int main(int argc, char **argv) {
    // Optional third argument: a short vocabulary prompt (product names) that biases recognition.
    if (argc != 3 && argc != 4) return 2;
    const std::string vocabulary = argc == 4 ? std::string(argv[3]).substr(0, 400) : std::string();
    whisper_log_set([](ggml_log_level, const char *, void *) {}, nullptr);
    const bool vad = std::string(argv[1]) == "vad";
    whisper_context *asr = nullptr;
    whisper_vad_context *detector = nullptr;
    if (vad) {
        auto p = whisper_vad_default_context_params(); p.n_threads = 1; p.use_gpu = false;
        detector = whisper_vad_init_from_file_with_params(argv[2], p);
        if (!detector) return 3;
    } else {
        auto p = whisper_context_default_params();
        asr = whisper_init_from_file_with_params(argv[2], p);
        if (!asr) return 3;
    }
    std::cout << "{\"ready\":true}" << std::endl;
    std::string line;
    while (std::getline(std::cin, line)) {
        size_t count;
        try { count = std::stoul(line); } catch (...) { break; }
        if (count == 0 && vad) { whisper_vad_reset_state(detector); std::cout << "{}" << std::endl; continue; }
        if (!count || count > 16000 * 180 || (vad && count != 512)) break;
        std::vector<float> samples(count);
        if (!std::cin.read(reinterpret_cast<char*>(samples.data()), count * sizeof(float))) break;
        bool valid = true;
        for (float f : samples) if (!std::isfinite(f) || std::abs(f) > 1.01f) valid = false;
        if (!valid) break;
        if (vad) {
            if (!whisper_vad_detect_speech_no_reset(detector, samples.data(), count)) break;
            int n = whisper_vad_n_probs(detector);
            std::cout << "{\"probability\":" << (n ? whisper_vad_probs(detector)[n-1] : 0) << "}" << std::endl;
        } else {
            const bool final = line.find(" final") != std::string::npos;
            auto p = whisper_full_default_params(final ? WHISPER_SAMPLING_BEAM_SEARCH : WHISPER_SAMPLING_GREEDY);
            if (final) { p.beam_search.beam_size = 5; p.temperature_inc = 0.0f; }
            p.n_threads = 4; p.language = "en"; p.translate = false; p.no_context = true;
            p.print_special = p.print_progress = p.print_realtime = p.print_timestamps = false;
            p.no_timestamps = true; p.suppress_blank = true;
            if (!vocabulary.empty()) p.initial_prompt = vocabulary.c_str();
            int result = whisper_full(asr, p, samples.data(), count);
            if (result) { std::cout << "{\"error\":\"recognition_failed\"}" << std::endl; continue; }
            std::string text; float no_speech = 0;
            int n = whisper_full_n_segments(asr);
            for (int i = 0; i < n; ++i) {
                text += whisper_full_get_segment_text(asr, i);
                no_speech = std::max(no_speech, whisper_full_get_segment_no_speech_prob(asr, i));
            }
            std::cout << "{\"text\":"; escaped(text);
            std::cout << ",\"no_speech\":" << no_speech << "}" << std::endl;
        }
    }
    if (asr) whisper_free(asr);
    if (detector) whisper_vad_free(detector);
}
