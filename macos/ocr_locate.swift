import Foundation
import Vision
import AppKit

// الاستعمال: ocr_locate <image> <word1> <word2> ...
// يطبع JSON: خطوط النص مع صناديقها النسبية (الأصل أعلى-يسار)
let args = CommandLine.arguments
guard args.count >= 3 else {
    print("{\"found\":false}")
    exit(0)
}
let imagePath = args[1]
let needles = Array(args[2...]).map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
guard let image = NSImage(contentsOfFile: imagePath),
      let tiff = image.tiffRepresentation,
      let bitmap = NSBitmapImageRep(data: tiff),
      let cg = bitmap.cgImage else {
    print("{\"found\":false,\"error\":\"image\"}")
    exit(0)
}

func normalize(_ s: String) -> String {
    var out = ""
    for scalar in s.unicodeScalars {
        let v = scalar.value
        if (v >= 0x064B && v <= 0x0652) || v == 0x0670 || v == 0x0640 { continue }
        var ch = Character(scalar)
        if "أإآٱ".contains(ch) { ch = "ا" }
        if ch == "ى" || ch == "ئ" { ch = "ي" }
        if ch == "ؤ" { ch = "و" }
        if ch == "ة" { ch = "ه" }
        out.append(ch)
    }
    return out
}

let wanted = needles.map(normalize)
let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["ar-SA"]
request.usesLanguageCorrection = false
let handler = VNImageRequestHandler(cgImage: cg, options: [:])
do {
    try handler.perform([request])
} catch {
    print("{\"found\":false,\"error\":\"vision\"}")
    exit(0)
}
let observations = request.results ?? []

struct Line: Encodable {
    let text: String
    let x: Double
    let y: Double
    let w: Double
    let h: Double
}
var lines: [Line] = []
var hitIndexes: [Int] = []
for (i, obs) in observations.enumerated() {
    guard let cand = obs.topCandidates(1).first else { continue }
    let bb = obs.boundingBox
    let line = Line(
        text: cand.string,
        x: Double(bb.minX),
        y: Double(1 - bb.maxY),
        w: Double(bb.width),
        h: Double(bb.height)
    )
    lines.append(line)
    let norm = normalize(cand.string)
    if wanted.contains(where: { !$0.isEmpty && norm.contains($0) }) {
        hitIndexes.append(i)
    }
}

struct Output: Encodable {
    let found: Bool
    let lines: [Line]
    let hits: [Int]
}
let out = Output(found: !hitIndexes.isEmpty, lines: lines, hits: hitIndexes)
if let data = try? JSONEncoder().encode(out) {
    print(String(data: data, encoding: .utf8) ?? "{\"found\":false}")
} else {
    print("{\"found\":false}")
}
