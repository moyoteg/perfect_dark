#!/usr/bin/env swift
// Generates a 1024×1024 PNG for the Perfect Dark Kit hub .app icon.
// Motif: launcher grid with three tool tiles + central KIT badge.

import AppKit
import Foundation

guard CommandLine.arguments.count >= 2 else {
	fputs("Usage: generate-kit-hub-icon.swift <output-png>\n", stderr)
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
let badge = NSBezierPath(roundedRect: canvas.insetBy(dx: 40, dy: 40), xRadius: 210, yRadius: 210)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context

rgba(8, 10, 18).setFill()
canvas.fill()
rgba(14, 18, 30).setFill()
badge.fill()

let inset = canvas.insetBy(dx: 120, dy: 120)
let tileW = (inset.width - 36) / 2
let tileH = (inset.height - 36) / 2

func drawTile(_ rect: NSRect, colors: [NSColor], symbol: String) {
	let path = NSBezierPath(roundedRect: rect, xRadius: 28, yRadius: 28)
	let grad = NSGradient(colors: colors)!
	grad.draw(in: rect, angle: 135)
	path.lineWidth = 3
	rgba(255, 255, 255, 0.18).setStroke()
	path.stroke()
	let attrs: [NSAttributedString.Key: Any] = [
		.font: NSFont.systemFont(ofSize: min(rect.width, rect.height) * 0.22, weight: .bold),
		.foregroundColor: rgba(255, 255, 255, 0.92),
	]
	let label = symbol as NSString
	let textSize = label.size(withAttributes: attrs)
	label.draw(
		at: NSPoint(x: rect.midX - textSize.width / 2, y: rect.midY - textSize.height / 2),
		withAttributes: attrs
	)
}

drawTile(
	NSRect(x: inset.minX, y: inset.minY + tileH + 36, width: tileW, height: tileH),
	colors: [rgba(46, 92, 210), rgba(24, 48, 120)],
	symbol: "MAP"
)
drawTile(
	NSRect(x: inset.minX + tileW + 36, y: inset.minY + tileH + 36, width: tileW, height: tileH),
	colors: [rgba(107, 70, 190), rgba(56, 34, 110)],
	symbol: "ANIM"
)
drawTile(
	NSRect(x: inset.minX, y: inset.minY, width: tileW, height: tileH),
	colors: [rgba(34, 150, 110), rgba(16, 72, 54)],
	symbol: "TEX"
)

let hubRect = NSRect(x: inset.minX + tileW + 36, y: inset.minY, width: tileW, height: tileH)
let hubPath = NSBezierPath(roundedRect: hubRect, xRadius: 28, yRadius: 28)
rgba(255, 255, 255, 0.08).setFill()
hubPath.fill()
hubPath.lineWidth = 4
rgba(122, 162, 255, 0.55).setStroke()
hubPath.stroke()
let kitAttrs: [NSAttributedString.Key: Any] = [
	.font: NSFont.systemFont(ofSize: 54, weight: .heavy),
	.foregroundColor: rgba(122, 162, 255),
]
let kit = "KIT" as NSString
let kitSize = kit.size(withAttributes: kitAttrs)
kit.draw(
	at: NSPoint(x: hubRect.midX - kitSize.width / 2, y: hubRect.midY - kitSize.height / 2 - 8),
	withAttributes: kitAttrs
)

let rim = NSBezierPath(roundedRect: canvas.insetBy(dx: 40, dy: 40), xRadius: 210, yRadius: 210)
rim.lineWidth = 6
rgba(255, 255, 255, 0.12).setStroke()
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
