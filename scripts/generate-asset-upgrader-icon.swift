#!/usr/bin/env swift
// Generates a 1024×1024 PNG for the Perfect Dark Kit Asset Upgrader .app icon.
// Motif: before/after texture split with upgrade arrow.

import AppKit
import Foundation

guard CommandLine.arguments.count >= 2 else {
	fputs("Usage: generate-asset-upgrader-icon.swift <output-png>\n", stderr)
	exit(1)
}

let outputURL = URL(fileURLWithPath: CommandLine.arguments[1])
let size = NSSize(width: 1024, height: 1024)

guard let rep = NSBitmapImageRep(
	bitmapDataPlanes: nil,
	pixelsWide: Int(size.width),
	pixelsHigh: Int(size.height),
	bitsPerSample: 8,
	samplesPerPixel: 4,
	hasAlpha: true,
	isPlanar: false,
	colorSpaceName: .deviceRGB,
	bytesPerRow: 0,
	bitsPerPixel: 0
), let context = NSGraphicsContext(bitmapImageRep: rep) else {
	fputs("Failed to create bitmap context.\n", stderr)
	exit(1)
}

func rgba(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> NSColor {
	NSColor(calibratedRed: r / 255, green: g / 255, blue: b / 255, alpha: a)
}

let canvas = NSRect(origin: .zero, size: size)
let squircle = canvas.insetBy(dx: 44, dy: 44)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context

rgba(10, 12, 18).setFill()
canvas.fill()

let badge = NSBezierPath(roundedRect: squircle, xRadius: 210, yRadius: 210)
rgba(18, 22, 32).setFill()
badge.fill()

let splitX = squircle.midX
let leftRect = NSRect(x: squircle.minX + 36, y: squircle.minY + 36, width: splitX - squircle.minX - 48, height: squircle.height - 72)
let rightRect = NSRect(x: splitX + 12, y: squircle.minY + 36, width: squircle.maxX - splitX - 48, height: squircle.height - 72)

func drawPixelBlock(in rect: NSRect, block: CGFloat, colors: [NSColor]) {
	for row in 0..<Int(rect.height / block) {
		for col in 0..<Int(rect.width / block) {
			let c = colors[(row + col) % colors.count]
			c.setFill()
			NSRect(
				x: rect.minX + CGFloat(col) * block,
				y: rect.minY + CGFloat(row) * block,
				width: block,
				height: block
			).fill()
		}
	}
}

drawPixelBlock(
	in: leftRect,
	block: 28,
	colors: [rgba(72, 58, 48), rgba(58, 46, 38), rgba(84, 66, 52), rgba(46, 38, 32)]
)

let sharp = NSGradient(colors: [
	rgba(120, 180, 255),
	rgba(72, 130, 220),
	rgba(48, 92, 168),
	rgba(28, 48, 96),
])!
sharp.draw(in: rightRect, angle: 45)

for frame in [leftRect, rightRect] {
	let p = NSBezierPath(roundedRect: frame, xRadius: 16, yRadius: 16)
	p.lineWidth = 3
	rgba(255, 255, 255, 0.15).setStroke()
	p.stroke()
}

let arrow = NSBezierPath()
arrow.move(to: NSPoint(x: splitX - 36, y: squircle.midY))
arrow.line(to: NSPoint(x: splitX + 36, y: squircle.midY))
arrow.line(to: NSPoint(x: splitX + 12, y: squircle.midY + 28))
arrow.move(to: NSPoint(x: splitX + 36, y: squircle.midY))
arrow.line(to: NSPoint(x: splitX + 12, y: squircle.midY - 28))
arrow.lineWidth = 10
rgba(255, 210, 96, 0.95).setStroke()
arrow.stroke()

let attrs: [NSAttributedString.Key: Any] = [
	.font: NSFont.systemFont(ofSize: 34, weight: .semibold),
	.foregroundColor: rgba(255, 255, 255, 0.88),
]
for (label, rect) in [("LOW", leftRect), ("HD", rightRect)] {
	let s = label as NSString
	let ts = s.size(withAttributes: attrs)
	s.draw(at: NSPoint(x: rect.midX - ts.width / 2, y: rect.maxY - ts.height - 16), withAttributes: attrs)
}

let rim = NSBezierPath(roundedRect: squircle, xRadius: 210, yRadius: 210)
rim.lineWidth = 6
rgba(255, 210, 96, 0.35).setStroke()
rim.stroke()

NSGraphicsContext.restoreGraphicsState()

guard let pngData = rep.representation(using: .png, properties: [:]) else {
	fputs("Failed to encode PNG.\n", stderr)
	exit(1)
}

do {
	try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
	try pngData.write(to: outputURL)
} catch {
	fputs("Failed to write icon: \(error)\n", stderr)
	exit(1)
}
