#!/usr/bin/env swift

import AppKit
import AVFoundation
import CoreVideo

let width = 1280
let height = 720
let fps: Int32 = 24
let seconds = 12
let output = URL(fileURLWithPath: CommandLine.arguments.dropFirst().first ?? "docs/proofpatch-demo.mp4")

try? FileManager.default.removeItem(at: output)
try FileManager.default.createDirectory(at: output.deletingLastPathComponent(), withIntermediateDirectories: true)

let writer = try AVAssetWriter(outputURL: output, fileType: .mp4)
let input = AVAssetWriterInput(
    mediaType: .video,
    outputSettings: [
        AVVideoCodecKey: AVVideoCodecType.h264,
        AVVideoWidthKey: width,
        AVVideoHeightKey: height,
        AVVideoCompressionPropertiesKey: [AVVideoAverageBitRateKey: 2_400_000],
    ]
)
input.expectsMediaDataInRealTime = false
let adaptor = AVAssetWriterInputPixelBufferAdaptor(
    assetWriterInput: input,
    sourcePixelBufferAttributes: [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32ARGB,
        kCVPixelBufferWidthKey as String: width,
        kCVPixelBufferHeightKey as String: height,
        kCVPixelBufferIOSurfacePropertiesKey as String: [:],
    ]
)
guard writer.canAdd(input) else { fatalError("Video input is unsupported") }
writer.add(input)
guard writer.startWriting() else { fatalError(writer.error?.localizedDescription ?? "Writer failed") }
writer.startSession(atSourceTime: .zero)

let bg = NSColor(calibratedRed: 7/255, green: 11/255, blue: 14/255, alpha: 1)
let panel = NSColor(calibratedRed: 13/255, green: 19/255, blue: 23/255, alpha: 1)
let line = NSColor(calibratedRed: 35/255, green: 49/255, blue: 57/255, alpha: 1)
let text = NSColor(calibratedRed: 237/255, green: 245/255, blue: 243/255, alpha: 1)
let muted = NSColor(calibratedRed: 145/255, green: 160/255, blue: 168/255, alpha: 1)
let teal = NSColor(calibratedRed: 57/255, green: 226/255, blue: 192/255, alpha: 1)
let amber = NSColor(calibratedRed: 243/255, green: 180/255, blue: 78/255, alpha: 1)

func attributes(_ size: CGFloat, color: NSColor, weight: NSFont.Weight = .regular, mono: Bool = false) -> [NSAttributedString.Key: Any] {
    let font = mono ? NSFont.monospacedSystemFont(ofSize: size, weight: weight) : NSFont.systemFont(ofSize: size, weight: weight)
    return [.font: font, .foregroundColor: color]
}

func drawText(_ value: String, x: CGFloat, y: CGFloat, size: CGFloat, color: NSColor = text, weight: NSFont.Weight = .regular, mono: Bool = false) {
    value.draw(at: NSPoint(x: x, y: y), withAttributes: attributes(size, color: color, weight: weight, mono: mono))
}

func rounded(_ rect: CGRect, radius: CGFloat, fill: NSColor, stroke: NSColor? = nil) {
    let path = NSBezierPath(roundedRect: rect, xRadius: radius, yRadius: radius)
    fill.setFill(); path.fill()
    if let stroke { stroke.setStroke(); path.lineWidth = 1; path.stroke() }
}

func ease(_ value: Double) -> CGFloat {
    let clamped = max(0, min(1, value))
    return CGFloat(clamped * clamped * (3 - 2 * clamped))
}

func frame(_ time: Double, context: CGContext) {
    let graphics = NSGraphicsContext(cgContext: context, flipped: false)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = graphics
    bg.setFill(); NSBezierPath(rect: CGRect(x: 0, y: 0, width: width, height: height)).fill()

    line.withAlphaComponent(0.18).setStroke()
    for x in stride(from: 0, through: width, by: 48) {
        let path = NSBezierPath(); path.move(to: NSPoint(x: x, y: 0)); path.line(to: NSPoint(x: x, y: height)); path.stroke()
    }
    for y in stride(from: 0, through: height, by: 48) {
        let path = NSBezierPath(); path.move(to: NSPoint(x: 0, y: y)); path.line(to: NSPoint(x: width, y: y)); path.stroke()
    }

    rounded(CGRect(x: 56, y: 642, width: 34, height: 34), radius: 8, fill: panel, stroke: teal)
    drawText("P", x: 68, y: 650, size: 16, color: teal, weight: .semibold, mono: true)
    drawText("ProofPatch", x: 103, y: 648, size: 22, weight: .semibold)
    drawText("EVIDENCE TRACE", x: 1060, y: 653, size: 12, color: muted, weight: .medium, mono: true)

    let scenes: [(Double, Double, String, String, String, NSColor)] = [
        (0, 3, "01", "Failure reproduced", "tests/test_textops.py::test_mask_email fails twice\nbefore the source snapshot is changed.", teal),
        (3, 6, "02", "Candidate 1 rejected", "Focused verification still fails. The diff and pytest\nevidence become feedback for one bounded retry.", amber),
        (6, 9, "03", "Candidate 2 verified", "The former failure passes. All 10 regression tests\nretain their identities and pass cleanly.", teal),
        (9, 12.1, "✓", "Review-ready patch", "Verified does not mean merged. The patch waits behind\nan explicit human approval gate.", teal),
    ]
    let active = scenes.first { time >= $0.0 && time < $0.1 } ?? scenes.last!
    let local = time - active.0
    let alpha = min(ease(local / 0.45), ease((active.1 - time) / 0.4))
    let yOffset = (1 - alpha) * -14

    graphics.cgContext.setAlpha(alpha)
    drawText("INCIDENT PP-008", x: 92, y: 560 + yOffset, size: 13, color: active.5, weight: .medium, mono: true)
    drawText(active.3, x: 92, y: 473 + yOffset, size: 58, weight: .bold)
    for (index, lineText) in active.4.split(separator: "\n").enumerated() {
        drawText(String(lineText), x: 94, y: 414 - CGFloat(index * 31) + yOffset, size: 21, color: muted)
    }
    rounded(CGRect(x: 930, y: 360 + yOffset, width: 214, height: 214), radius: 107, fill: active.5.withAlphaComponent(0.10), stroke: active.5)
    let iconWidth = (active.2 as NSString).size(withAttributes: attributes(58, color: active.5, weight: .bold, mono: true)).width
    drawText(active.2, x: 1037 - iconWidth / 2, y: 434 + yOffset, size: 58, color: active.5, weight: .bold, mono: true)
    graphics.cgContext.setAlpha(1)

    let nodes = ["REPRODUCE", "INVESTIGATE", "REPAIR", "VERIFY", "REVIEW"]
    let completed = min(4, Int(time / 2.5))
    for (index, node) in nodes.enumerated() {
        let x = 92 + CGFloat(index) * 225
        let nodeColor = index <= completed ? teal : muted
        rounded(CGRect(x: x, y: 175, width: 172, height: 62), radius: 9, fill: index <= completed ? teal.withAlphaComponent(0.10) : panel, stroke: nodeColor.withAlphaComponent(0.7))
        drawText(node, x: x + 19, y: 198, size: 12, color: nodeColor, weight: .medium, mono: true)
        if index < nodes.count - 1 {
            nodeColor.withAlphaComponent(0.55).setStroke()
            let path = NSBezierPath(); path.move(to: NSPoint(x: x + 172, y: 206)); path.line(to: NSPoint(x: x + 211, y: 206)); path.stroke()
        }
    }

    rounded(CGRect(x: 92, y: 92, width: 1052, height: 5), radius: 2.5, fill: line)
    rounded(CGRect(x: 92, y: 92, width: 1052 * CGFloat(time / Double(seconds)), height: 5), radius: 2.5, fill: teal)
    drawText("failure → evidence → bounded retry → verified → human review", x: 92, y: 54, size: 12, color: muted, mono: true)
    NSGraphicsContext.restoreGraphicsState()
}

guard let pool = adaptor.pixelBufferPool else { fatalError("Pixel buffer pool unavailable") }
for index in 0..<(seconds * Int(fps)) {
    while !input.isReadyForMoreMediaData { Thread.sleep(forTimeInterval: 0.002) }
    var buffer: CVPixelBuffer?
    guard CVPixelBufferPoolCreatePixelBuffer(nil, pool, &buffer) == kCVReturnSuccess, let buffer else { fatalError("Could not allocate frame") }
    CVPixelBufferLockBaseAddress(buffer, [])
    let context = CGContext(
        data: CVPixelBufferGetBaseAddress(buffer),
        width: width,
        height: height,
        bitsPerComponent: 8,
        bytesPerRow: CVPixelBufferGetBytesPerRow(buffer),
        space: CGColorSpaceCreateDeviceRGB(),
        bitmapInfo: CGImageAlphaInfo.premultipliedFirst.rawValue
    )!
    frame(Double(index) / Double(fps), context: context)
    CVPixelBufferUnlockBaseAddress(buffer, [])
    guard adaptor.append(buffer, withPresentationTime: CMTime(value: Int64(index), timescale: fps)) else { fatalError(writer.error?.localizedDescription ?? "Frame append failed") }
}

input.markAsFinished()
let finished = DispatchSemaphore(value: 0)
writer.finishWriting { finished.signal() }
finished.wait()
guard writer.status == .completed else { fatalError(writer.error?.localizedDescription ?? "Video export failed") }
print(output.path)
