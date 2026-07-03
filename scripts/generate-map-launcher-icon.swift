#!/usr/bin/env swift
// Generates a 1024×1024 PNG for the PD Map Launcher .app icon.
// Motif: stacked launch cards with a play glyph (curriculum / test-map launcher).

import AppKit
import Foundation

guard CommandLine.arguments.count >= 2 else {
	fputs("Usage: generate-map-launcher-icon.swift <output-png>\n", stderr)
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
let inset = canvas.insetBy(dx: 48, dy: 48)
let badge = NSBezierPath(roundedRect: inset, xRadius: 200, yRadius: 200)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context

rgba(10, 14, 22).setFill()
canvas.fill()

rgba(16, 22, 34).setFill()
badge.fill()

// Stacked launch cards (left side)
let cardW = inset.width * 0.52
let cardH = inset.height * 0.16
let cardX = inset.minX + 56
let cardColors: [(NSColor, NSColor)] = [
	(rgba(70, 130, 255, 0.35), rgba(70, 130, 255, 0.12)),
	(rgba(87, 217, 119, 0.35), rgba(87, 217, 119, 0.10)),
	(rgba(255, 180, 72, 0.35), rgba(255, 180, 72, 0.10)),
]
for (index, colors) in cardColors.enumerated() {
	let y = inset.maxY - 140 - CGFloat(index) * (cardH + 28)
	let cardRect = NSRect(x: cardX, y: y - cardH, width: cardW, height: cardH)
	let card = NSBezierPath(roundedRect: cardRect, xRadius: 22, yRadius: 22)
	colors.1.setFill()
	card.fill()
	colors.0.setStroke()
	card.lineWidth = 3
	card.stroke()

	// Mini pad dots on each card
	let dotY = cardRect.midY
	for dotX in [0.18, 0.42, 0.66] {
		let px = cardRect.minX + cardRect.width * dotX
		let dot = NSBezierPath(ovalIn: NSRect(x: px - 10, y: dotY - 10, width: 20, height: 20))
		rgba(255, 255, 255, 0.75).setFill()
		dot.fill()
	}
}

// Play triangle (launch action)
let triCenter = NSPoint(x: inset.maxX - 170, y: inset.midY - 10)
let triH: CGFloat = 220
let triW: CGFloat = 190
let tri = NSBezierPath()
tri.move(to: NSPoint(x: triCenter.x - triW * 0.45, y: triCenter.y - triH * 0.5))
tri.line(to: NSPoint(x: triCenter.x - triW * 0.45, y: triCenter.y + triH * 0.5))
tri.line(to: NSPoint(x: triCenter.x + triW * 0.55, y: triCenter.y))
tri.close()
context.cgContext.saveGState()
context.cgContext.setShadow(offset: CGSize(width: 0, height: -10), blur: 24, color: rgba(0, 0, 0, 0.45).cgColor)
rgba(87, 217, 119, 0.95).setFill()
tri.fill()
context.cgContext.restoreGState()
rgba(255, 255, 255, 0.35).setStroke()
tri.lineWidth = 4
tri.stroke()

// Title strip
let titleRect = NSRect(x: inset.minX + 40, y: inset.minY + 48, width: inset.width - 80, height: 56)
let titlePath = NSBezierPath(roundedRect: titleRect, xRadius: 14, yRadius: 14)
rgba(255, 255, 255, 0.10).setFill()
titlePath.fill()
rgba(255, 255, 255, 0.88).setFill()
let attrs: [NSAttributedString.Key: Any] = [
	.font: NSFont.systemFont(ofSize: 26, weight: .semibold),
]
let label = "MAP LAUNCHER" as NSString
let textSize = label.size(withAttributes: attrs)
label.draw(
	at: NSPoint(x: titleRect.midX - textSize.width / 2, y: titleRect.midY - textSize.height / 2),
	withAttributes: attrs
)

let outer = NSBezierPath(roundedRect: inset, xRadius: 200, yRadius: 200)
outer.lineWidth = 8
rgba(255, 255, 255, 0.12).setStroke()
outer.stroke()

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
