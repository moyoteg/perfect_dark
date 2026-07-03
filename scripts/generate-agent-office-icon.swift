#!/usr/bin/env swift
// 1024×1024 icon for Virtual Agent Office — dataDyne G5 corporate + terminal motif.

import AppKit
import Foundation

guard CommandLine.arguments.count >= 2 else {
	fputs("Usage: generate-agent-office-icon.swift <output-png>\n", stderr)
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

rgba(8, 12, 20).setFill()
canvas.fill()

// Corporate gradient panel (dataDyne teal)
let grad = NSGradient(colors: [
	rgba(12, 28, 48),
	rgba(18, 52, 72),
	rgba(10, 22, 38),
])
grad?.draw(in: badge, angle: 135)

// Office window grid (G5 tower glass)
let gridInset = inset.insetBy(dx: 72, dy: 88)
let cols = 4
let rows = 3
let cellW = gridInset.width / CGFloat(cols)
let cellH = gridInset.height / CGFloat(rows)
for row in 0..<rows {
	for col in 0..<cols {
		let x = gridInset.minX + CGFloat(col) * cellW + 10
		let y = gridInset.maxY - CGFloat(row + 1) * cellH + 10
		let rect = NSRect(x: x, y: y, width: cellW - 20, height: cellH - 20)
		let pane = NSBezierPath(roundedRect: rect, xRadius: 14, yRadius: 14)
		let lit = (row + col) % 3 == 0
		(lit ? rgba(40, 180, 210, 0.22) : rgba(255, 255, 255, 0.06)).setFill()
		pane.fill()
		rgba(255, 255, 255, lit ? 0.18 : 0.08).setStroke()
		pane.lineWidth = 2
		pane.stroke()
	}
}

// Terminal / monitor (center-bottom)
let monW = inset.width * 0.46
let monH = inset.height * 0.28
let monRect = NSRect(
	x: inset.midX - monW / 2,
	y: inset.minY + 120,
	width: monW,
	height: monH
)
let monitor = NSBezierPath(roundedRect: monRect, xRadius: 24, yRadius: 24)
rgba(6, 10, 16).setFill()
monitor.fill()
rgba(60, 200, 230, 0.55).setStroke()
monitor.lineWidth = 5
monitor.stroke()

// Screen glow + code lines
let screen = monRect.insetBy(dx: 18, dy: 18)
rgba(20, 80, 100, 0.35).setFill()
NSBezierPath(roundedRect: screen, xRadius: 12, yRadius: 12).fill()
for i in 0..<5 {
	let ly = screen.maxY - 28 - CGFloat(i) * 22
	let lw = screen.width * (0.55 + CGFloat(i % 3) * 0.12)
	let line = NSBezierPath(roundedRect: NSRect(x: screen.minX + 16, y: ly, width: lw, height: 10), xRadius: 5, yRadius: 5)
	rgba(80, 220, 255, 0.65 - CGFloat(i) * 0.08).setFill()
	line.fill()
}

// Agent silhouette at desk
let head = NSBezierPath(ovalIn: NSRect(x: inset.midX - 36, y: monRect.maxY + 36, width: 72, height: 72))
rgba(230, 240, 255, 0.92).setFill()
head.fill()
let shoulders = NSBezierPath()
shoulders.move(to: NSPoint(x: inset.midX - 70, y: monRect.maxY + 28))
shoulders.line(to: NSPoint(x: inset.midX + 70, y: monRect.maxY + 28))
shoulders.line(to: NSPoint(x: inset.midX + 48, y: monRect.maxY + 8))
shoulders.line(to: NSPoint(x: inset.midX - 48, y: monRect.maxY + 8))
shoulders.close()
rgba(200, 210, 230, 0.85).setFill()
shoulders.fill()

// "VA" monogram badge (top-right)
let badgeRect = NSRect(x: inset.maxX - 168, y: inset.maxY - 168, width: 120, height: 120)
let monoBadge = NSBezierPath(ovalIn: badgeRect)
rgba(0, 180, 210, 0.25).setFill()
monoBadge.fill()
rgba(0, 220, 255, 0.7).setStroke()
monoBadge.lineWidth = 4
monoBadge.stroke()

let attrs: [NSAttributedString.Key: Any] = [
	.font: NSFont.systemFont(ofSize: 44, weight: .bold),
	.foregroundColor: rgba(180, 245, 255),
]
let va = "VA" as NSString
let vaSize = va.size(withAttributes: attrs)
va.draw(at: NSPoint(x: badgeRect.midX - vaSize.width / 2, y: badgeRect.midY - vaSize.height / 2 - 2), withAttributes: attrs)

NSGraphicsContext.restoreGraphicsState()

guard let png = rep.representation(using: .png, properties: [:]) else {
	fputs("Failed to encode PNG.\n", stderr)
	exit(1)
}
do {
	try png.write(to: outputURL)
} catch {
	fputs("Write failed: \(error)\n", stderr)
	exit(1)
}
