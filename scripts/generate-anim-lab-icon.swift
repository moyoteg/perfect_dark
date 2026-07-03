#!/usr/bin/env swift
// Generates a 1024×1024 PNG for the Perfect Dark Animation Lab .app icon.
// Motif: film-strip parade frames + play glyph (symbol-only — readable at 16px).

import AppKit
import Foundation

guard CommandLine.arguments.count >= 2 else {
	fputs("Usage: generate-anim-lab-icon.swift <output-png>\n", stderr)
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

func fillLinearGradient(in rect: NSRect, start: NSPoint, end: NSPoint, colors: [NSColor]) {
	let gradient = NSGradient(colors: colors)!
	gradient.draw(in: rect, angle: atan2(end.y - start.y, end.x - start.x) * 180 / .pi + 90)
}

func fillRadialGradient(in rect: NSRect, center: NSPoint, radius: CGFloat, colors: [NSColor], locations: [CGFloat]) {
	let gradient = NSGradient(colors: colors, atLocations: locations, colorSpace: .deviceRGB)!
	gradient.draw(fromCenter: center, radius: 0, toCenter: center, radius: radius, options: [])
}

/// Minimal guard stick figure for parade frame silhouettes.
func drawGuardSilhouette(at center: NSPoint, scale: CGFloat, pose: Int, color: NSColor) {
	let s = scale
	color.setFill()
	color.setStroke()

	switch pose {
	case 0: // standing at attention
		let head = NSBezierPath(ovalIn: NSRect(x: center.x - 10 * s, y: center.y + 28 * s, width: 20 * s, height: 20 * s))
		head.fill()
		let body = NSBezierPath()
		body.move(to: NSPoint(x: center.x, y: center.y + 26 * s))
		body.line(to: NSPoint(x: center.x, y: center.y - 8 * s))
		body.lineWidth = 7 * s
		body.stroke()
		for (dx, dy) in [(-14.0, -22.0), (14.0, -22.0)] {
			let leg = NSBezierPath()
			leg.move(to: NSPoint(x: center.x, y: center.y - 8 * s))
			leg.line(to: NSPoint(x: center.x + dx * s, y: center.y + dy * s))
			leg.lineWidth = 6 * s
			leg.stroke()
		}
	case 1: // marching left leg forward
		let head = NSBezierPath(ovalIn: NSRect(x: center.x - 10 * s, y: center.y + 26 * s, width: 20 * s, height: 20 * s))
		head.fill()
		let body = NSBezierPath()
		body.move(to: NSPoint(x: center.x, y: center.y + 24 * s))
		body.line(to: NSPoint(x: center.x + 4 * s, y: center.y - 6 * s))
		body.lineWidth = 7 * s
		body.stroke()
		let l1 = NSBezierPath()
		l1.move(to: NSPoint(x: center.x + 4 * s, y: center.y - 6 * s))
		l1.line(to: NSPoint(x: center.x - 10 * s, y: center.y - 28 * s))
		l1.lineWidth = 6 * s
		l1.stroke()
		let l2 = NSBezierPath()
		l2.move(to: NSPoint(x: center.x + 4 * s, y: center.y - 6 * s))
		l2.line(to: NSPoint(x: center.x + 18 * s, y: center.y - 18 * s))
		l2.lineWidth = 6 * s
		l2.stroke()
	case 2: // rifle salute / aim
		let head = NSBezierPath(ovalIn: NSRect(x: center.x - 10 * s, y: center.y + 24 * s, width: 20 * s, height: 20 * s))
		head.fill()
		let body = NSBezierPath()
		body.move(to: NSPoint(x: center.x, y: center.y + 22 * s))
		body.line(to: NSPoint(x: center.x, y: center.y - 10 * s))
		body.lineWidth = 7 * s
		body.stroke()
		let arm = NSBezierPath()
		arm.move(to: NSPoint(x: center.x, y: center.y + 10 * s))
		arm.line(to: NSPoint(x: center.x + 28 * s, y: center.y + 18 * s))
		arm.lineWidth = 5 * s
		arm.stroke()
	default: // crouch / roll pose
		let head = NSBezierPath(ovalIn: NSRect(x: center.x - 9 * s, y: center.y + 12 * s, width: 18 * s, height: 18 * s))
		head.fill()
		let body = NSBezierPath()
		body.move(to: NSPoint(x: center.x, y: center.y + 10 * s))
		body.line(to: NSPoint(x: center.x + 16 * s, y: center.y - 4 * s))
		body.lineWidth = 7 * s
		body.stroke()
	}
}

let canvas = NSRect(origin: .zero, size: size)
let squircle = canvas.insetBy(dx: 36, dy: 36)
let corner = squircle.width * 0.223
let badge = NSBezierPath(roundedRect: squircle, xRadius: corner, yRadius: corner)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
context.imageInterpolation = .high

// Background — matches Animation Lab UI (#0a0a12 + violet lift)
fillLinearGradient(
	in: canvas,
	start: NSPoint(x: canvas.minX, y: canvas.maxY),
	end: NSPoint(x: canvas.maxX, y: canvas.minY),
	colors: [
		rgba(10, 10, 18),
		rgba(26, 26, 64),
		rgba(10, 10, 18),
	]
)

badge.addClip()
fillLinearGradient(
	in: squircle,
	start: NSPoint(x: squircle.minX, y: squircle.maxY),
	end: NSPoint(x: squircle.maxX, y: squircle.minY),
	colors: [
		rgba(18, 18, 28),
		rgba(20, 24, 42),
		rgba(14, 14, 24),
	]
)

// Soft accent glow (Animation Lab --accent #6b8cff)
fillRadialGradient(
	in: squircle,
	center: NSPoint(x: squircle.midX, y: squircle.midY),
	radius: squircle.width * 0.48,
	colors: [
		rgba(107, 140, 255, 0.22),
		rgba(107, 140, 255, 0.06),
		rgba(0, 0, 0, 0),
	],
	locations: [0, 0.5, 1]
)

// Film strip band
let stripH = squircle.height * 0.38
let stripW = squircle.width * 0.82
let stripRect = NSRect(
	x: squircle.midX - stripW / 2,
	y: squircle.midY - stripH / 2,
	width: stripW,
	height: stripH
)
let stripPath = NSBezierPath(roundedRect: stripRect, xRadius: 18, yRadius: 18)
rgba(8, 8, 14).setFill()
stripPath.fill()
rgba(42, 42, 64).setStroke()
stripPath.lineWidth = 3
stripPath.stroke()

// Perforations (classic film strip — --live dot #ffb347)
let perfH: CGFloat = 14
let perfCount = 14
let perfSpacing = stripRect.width / CGFloat(perfCount + 1)
for i in 1...perfCount {
	let cx = stripRect.minX + perfSpacing * CGFloat(i)
	for py in [stripRect.maxY + 6, stripRect.minY - perfH - 6] {
		let perf = NSBezierPath(roundedRect: NSRect(x: cx - 10, y: py, width: 20, height: perfH), xRadius: 4, yRadius: 4)
		rgba(255, 179, 71, 0.92).setFill()
		perf.fill()
	}
}

// Frame cells inside the strip
let frameCount = 5
let framePad: CGFloat = 22
let frameGap: CGFloat = 10
let innerStrip = stripRect.insetBy(dx: framePad, dy: framePad)
let frameW = (innerStrip.width - frameGap * CGFloat(frameCount - 1)) / CGFloat(frameCount)
let guardColor = rgba(107, 140, 255, 0.88)
let altGuard = rgba(79, 209, 165, 0.82)

for i in 0..<frameCount {
	let fx = innerStrip.minX + CGFloat(i) * (frameW + frameGap)
	let frameRect = NSRect(x: fx, y: innerStrip.minY, width: frameW, height: innerStrip.height)
	let framePath = NSBezierPath(roundedRect: frameRect, xRadius: 8, yRadius: 8)
	rgba(24, 24, 40).setFill()
	framePath.fill()
	rgba(58, 74, 128, 0.55).setStroke()
	framePath.lineWidth = 2
	framePath.stroke()

	let guardCenter = NSPoint(x: frameRect.midX, y: frameRect.midY - 8)
	drawGuardSilhouette(at: guardCenter, scale: frameW / 120, pose: i % 4, color: i == 2 ? altGuard : guardColor)
}

// Center play triangle (parade playback)
let triH = stripH * 0.55
let triW = triH * 0.92
let triCenter = NSPoint(x: squircle.midX + triW * 0.04, y: squircle.midY - 4)
let tri = NSBezierPath()
tri.move(to: NSPoint(x: triCenter.x - triW * 0.46, y: triCenter.y - triH * 0.5))
tri.line(to: NSPoint(x: triCenter.x - triW * 0.46, y: triCenter.y + triH * 0.5))
tri.line(to: NSPoint(x: triCenter.x + triW * 0.54, y: triCenter.y))
tri.close()

context.cgContext.saveGState()
context.cgContext.setShadow(offset: CGSize(width: 0, height: -8), blur: 24, color: rgba(0, 0, 0, 0.55).cgColor)
rgba(255, 255, 255, 0.08).setFill()
tri.fill()
context.cgContext.restoreGState()

context.cgContext.saveGState()
tri.addClip()
fillLinearGradient(
	in: NSRect(x: triCenter.x - triW, y: triCenter.y - triH, width: triW * 2, height: triH * 2),
	start: NSPoint(x: triCenter.x - triW * 0.4, y: triCenter.y + triH * 0.5),
	end: NSPoint(x: triCenter.x + triW * 0.5, y: triCenter.y - triH * 0.4),
	colors: [
		rgba(255, 255, 255, 0.95),
		rgba(107, 140, 255, 0.92),
		rgba(47, 78, 196, 0.95),
	]
)
context.cgContext.restoreGState()

// Specular sheen
context.cgContext.saveGState()
badge.addClip()
let sheen = NSBezierPath()
sheen.move(to: NSPoint(x: squircle.minX, y: squircle.maxY))
sheen.line(to: NSPoint(x: squircle.maxX, y: squircle.maxY))
sheen.line(to: NSPoint(x: squircle.minX + squircle.width * 0.5, y: squircle.minY))
sheen.close()
rgba(255, 255, 255, 0.06).setFill()
sheen.fill()
context.cgContext.restoreGState()

// Outer rim
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
let rim = NSBezierPath(roundedRect: squircle, xRadius: corner, yRadius: corner)
rim.lineWidth = 3
rgba(255, 255, 255, 0.12).setStroke()
rim.stroke()
let innerRim = NSBezierPath(roundedRect: squircle.insetBy(dx: 5, dy: 5), xRadius: corner - 5, yRadius: corner - 5)
innerRim.lineWidth = 2
rgba(107, 140, 255, 0.28).setStroke()
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
