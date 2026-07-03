#!/usr/bin/env swift
// Generates a 1024×1024 PNG for the LLM Play .app icon.
// Symbol-only design — no text (readable at 16px through 512px).

import AppKit
import Foundation

guard CommandLine.arguments.count >= 2 else {
	fputs("Usage: generate-llm-play-icon.swift <output-png>\n", stderr)
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

func lerp(_ a: CGFloat, _ b: CGFloat, _ t: CGFloat) -> CGFloat {
	a + (b - a) * t
}

func fillLinearGradient(in rect: NSRect, start: NSPoint, end: NSPoint, colors: [NSColor]) {
	let gradient = NSGradient(colors: colors)!
	gradient.draw(in: rect, angle: atan2(end.y - start.y, end.x - start.x) * 180 / .pi + 90)
}

func fillRadialGradient(in rect: NSRect, center: NSPoint, radius: CGFloat, colors: [NSColor], locations: [CGFloat]) {
	let gradient = NSGradient(colors: colors, atLocations: locations, colorSpace: .deviceRGB)!
	gradient.draw(fromCenter: center, radius: 0, toCenter: center, radius: radius, options: [])
}

let canvas = NSRect(origin: .zero, size: size)
let squircle = canvas.insetBy(dx: 36, dy: 36)
let corner = squircle.width * 0.223
let badge = NSBezierPath(roundedRect: squircle, xRadius: corner, yRadius: corner)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
context.imageInterpolation = .high

// --- Background (deep space + subtle violet lift) ---
fillLinearGradient(
	in: canvas,
	start: NSPoint(x: canvas.minX, y: canvas.maxY),
	end: NSPoint(x: canvas.maxX, y: canvas.minY),
	colors: [
		rgba(6, 8, 18),
		rgba(14, 10, 32),
		rgba(8, 14, 28),
	]
)

badge.addClip()
fillLinearGradient(
	in: squircle,
	start: NSPoint(x: squircle.minX, y: squircle.maxY),
	end: NSPoint(x: squircle.maxX, y: squircle.minY),
	colors: [
		rgba(18, 22, 44),
		rgba(10, 12, 26),
		rgba(22, 16, 48),
	]
)

// Soft ambient glow behind the mark
fillRadialGradient(
	in: squircle,
	center: NSPoint(x: squircle.midX, y: squircle.midY + 20),
	radius: squircle.width * 0.42,
	colors: [
		rgba(45, 212, 191, 0.28),
		rgba(167, 139, 250, 0.12),
		rgba(0, 0, 0, 0),
	],
	locations: [0, 0.45, 1]
)

// --- Neural orbit (three nodes + curved synapse paths) ---
let hub = NSPoint(x: squircle.midX, y: squircle.midY - 8)
let orbitR = squircle.width * 0.31
let nodeAngles: [CGFloat] = [110, -10, 230].map { $0 * .pi / 180 }
let nodes: [NSPoint] = nodeAngles.map { a in
	NSPoint(x: hub.x + cos(a) * orbitR, y: hub.y + sin(a) * orbitR)
}

func drawSynapse(from a: NSPoint, to b: NSPoint, width: CGFloat, color: NSColor) {
	let mid = NSPoint(x: (a.x + b.x) / 2, y: (a.y + b.y) / 2)
	let dx = b.x - a.x
	let dy = b.y - a.y
	let len = max(sqrt(dx * dx + dy * dy), 1)
	let nx = -dy / len
	let ny = dx / len
	let bend = orbitR * 0.22
	let c1 = NSPoint(x: mid.x + nx * bend, y: mid.y + ny * bend)

	let path = NSBezierPath()
	path.move(to: a)
	path.curve(to: b, controlPoint1: c1, controlPoint2: c1)
	path.lineWidth = width
	color.setStroke()
	path.stroke()
}

for i in 0..<nodes.count {
	let next = nodes[(i + 1) % nodes.count]
	drawSynapse(from: nodes[i], to: next, width: 7, color: rgba(56, 189, 248, 0.35))
	drawSynapse(from: hub, to: nodes[i], width: 5, color: rgba(45, 212, 191, 0.42))
}

for (idx, p) in nodes.enumerated() {
	let r: CGFloat = idx == 1 ? 26 : 22
	let glow = NSBezierPath(ovalIn: NSRect(x: p.x - r * 1.8, y: p.y - r * 1.8, width: r * 3.6, height: r * 3.6))
	rgba(45, 212, 191, 0.16).setFill()
	glow.fill()

	let dot = NSBezierPath(ovalIn: NSRect(x: p.x - r, y: p.y - r, width: r * 2, height: r * 2))
	fillRadialGradient(
		in: dot.bounds,
		center: NSPoint(x: p.x - r * 0.25, y: p.y + r * 0.25),
		radius: r * 2.2,
		colors: [rgba(110, 231, 183), rgba(45, 212, 191), rgba(14, 116, 144)],
		locations: [0, 0.55, 1]
	)
	rgba(255, 255, 255, 0.55).setStroke()
	dot.lineWidth = 2.5
	dot.stroke()
}

// Hub node (synapse center — sits under play triangle)
let hubR: CGFloat = 22
let hubGlow = NSBezierPath(ovalIn: NSRect(x: hub.x - hubR * 2.4, y: hub.y - hubR * 2.4, width: hubR * 4.8, height: hubR * 4.8))
rgba(167, 139, 250, 0.18).setFill()
hubGlow.fill()
let hubDot = NSBezierPath(ovalIn: NSRect(x: hub.x - hubR, y: hub.y - hubR, width: hubR * 2, height: hubR * 2))
fillRadialGradient(
	in: hubDot.bounds,
	center: NSPoint(x: hub.x - hubR * 0.2, y: hub.y + hubR * 0.3),
	radius: hubR * 2.4,
	colors: [rgba(196, 181, 253), rgba(124, 58, 237), rgba(49, 46, 129)],
	locations: [0, 0.5, 1]
)

// --- Play triangle (primary glyph) ---
let triH = squircle.height * 0.36
let triW = triH * 0.95
let triCenter = NSPoint(x: hub.x + triW * 0.06, y: hub.y - 4)
let tri = NSBezierPath()
tri.move(to: NSPoint(x: triCenter.x - triW * 0.44, y: triCenter.y - triH * 0.5))
tri.line(to: NSPoint(x: triCenter.x - triW * 0.44, y: triCenter.y + triH * 0.5))
tri.line(to: NSPoint(x: triCenter.x + triW * 0.56, y: triCenter.y))
tri.close()

context.cgContext.saveGState()
context.cgContext.setShadow(offset: CGSize(width: 0, height: -12), blur: 32, color: rgba(0, 0, 0, 0.5).cgColor)
rgba(255, 255, 255, 0.06).setFill()
tri.fill()
context.cgContext.restoreGState()

context.cgContext.saveGState()
tri.addClip()
fillLinearGradient(
	in: NSRect(x: triCenter.x - triW, y: triCenter.y - triH, width: triW * 2, height: triH * 2),
	start: NSPoint(x: triCenter.x - triW * 0.5, y: triCenter.y + triH * 0.6),
	end: NSPoint(x: triCenter.x + triW * 0.6, y: triCenter.y - triH * 0.5),
	colors: [
		rgba(255, 255, 255),
		rgba(167, 243, 208),
		rgba(16, 185, 129),
	]
)
context.cgContext.restoreGState()

// Inner highlight on play face
let shine = NSBezierPath()
shine.move(to: NSPoint(x: triCenter.x - triW * 0.30, y: triCenter.y + triH * 0.08))
shine.line(to: NSPoint(x: triCenter.x - triW * 0.30, y: triCenter.y + triH * 0.36))
shine.line(to: NSPoint(x: triCenter.x + triW * 0.02, y: triCenter.y + triH * 0.06))
shine.close()
rgba(255, 255, 255, 0.42).setFill()
shine.fill()

// --- Specular top-left sheen ---
context.cgContext.restoreGState()
context.cgContext.saveGState()
badge.addClip()
let sheen = NSBezierPath()
sheen.move(to: NSPoint(x: squircle.minX, y: squircle.maxY))
sheen.line(to: NSPoint(x: squircle.maxX, y: squircle.maxY))
sheen.line(to: NSPoint(x: squircle.minX + squircle.width * 0.55, y: squircle.minY))
sheen.close()
rgba(255, 255, 255, 0.07).setFill()
sheen.fill()
context.cgContext.restoreGState()

// --- Outer rim (macOS squircle edge) ---
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
let rim = NSBezierPath(roundedRect: squircle, xRadius: corner, yRadius: corner)
rim.lineWidth = 3
rgba(255, 255, 255, 0.14).setStroke()
rim.stroke()
let innerRim = NSBezierPath(roundedRect: squircle.insetBy(dx: 5, dy: 5), xRadius: corner - 5, yRadius: corner - 5)
innerRim.lineWidth = 2
rgba(45, 212, 191, 0.18).setStroke()
innerRim.stroke()
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
