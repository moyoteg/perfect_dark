#!/usr/bin/env swift

import AppKit
import Foundation

guard CommandLine.arguments.count >= 3 else {
	fputs("Usage: generate-perfectdark-icon.swift <source-image> <output-png>\n", stderr)
	exit(1)
}

let sourceImagePath = CommandLine.arguments[1]
let outputPath = CommandLine.arguments[2]
let sourceURL = URL(fileURLWithPath: sourceImagePath)
let outputURL = URL(fileURLWithPath: outputPath)

let size = NSSize(width: 1024, height: 1024)

guard let sourceImage = NSImage(contentsOf: sourceURL) else {
	fputs("Failed to load source image at \(sourceImagePath).\n", stderr)
	exit(1)
}

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
) else {
	fputs("Failed to create bitmap image representation.\n", stderr)
	exit(1)
}

guard let context = NSGraphicsContext(bitmapImageRep: rep) else {
	fputs("Failed to create graphics context.\n", stderr)
	exit(1)
}

func rgba(_ red: CGFloat, _ green: CGFloat, _ blue: CGFloat, _ alpha: CGFloat = 1.0) -> NSColor {
	NSColor(calibratedRed: red / 255.0, green: green / 255.0, blue: blue / 255.0, alpha: alpha)
}

func point(_ x: CGFloat, _ y: CGFloat) -> NSPoint {
	NSPoint(x: x, y: y)
}

func drawAspectFill(image: NSImage, in targetRect: NSRect, horizontalBias: CGFloat, verticalBias: CGFloat) {
	let sourceSize = image.size
	let scale = max(targetRect.width / sourceSize.width, targetRect.height / sourceSize.height)
	let scaledSize = NSSize(width: sourceSize.width * scale, height: sourceSize.height * scale)
	let overflowX = max(0, scaledSize.width - targetRect.width)
	let overflowY = max(0, scaledSize.height - targetRect.height)
	let drawRect = NSRect(
		x: targetRect.minX - (overflowX * horizontalBias),
		y: targetRect.minY - (overflowY * verticalBias),
		width: scaledSize.width,
		height: scaledSize.height
	)

	image.draw(
		in: drawRect,
		from: NSRect(origin: .zero, size: sourceSize),
		operation: .sourceOver,
		fraction: 1.0
	)
}

let canvas = NSRect(origin: .zero, size: size)
let insetRect = canvas.insetBy(dx: 44, dy: 44)
let badge = NSBezierPath(roundedRect: insetRect, xRadius: 220, yRadius: 220)

NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = context
context.imageInterpolation = .high

rgba(0, 0, 0, 0).setFill()
canvas.fill()

rgba(7, 8, 12).setFill()
badge.fill()

context.cgContext.saveGState()
badge.addClip()
drawAspectFill(image: sourceImage, in: insetRect, horizontalBias: 0.08, verticalBias: 0.5)

let vignette = NSGradient(colors: [
	rgba(0, 0, 0, 0.00),
	rgba(0, 0, 0, 0.18),
	rgba(0, 0, 0, 0.48),
])!
vignette.draw(
	fromCenter: point(512, 560),
	radius: 280,
	toCenter: point(512, 560),
	radius: 740,
	options: [.drawsBeforeStartingLocation, .drawsAfterEndingLocation]
)

let gloss = NSGradient(colors: [
	rgba(255, 255, 255, 0.16),
	rgba(255, 255, 255, 0.03),
	rgba(255, 255, 255, 0.0),
])!
gloss.draw(in: NSBezierPath(rect: NSRect(x: 0, y: 620, width: 1024, height: 340)), angle: 90)

context.cgContext.restoreGState()

let outerBorder = NSBezierPath(roundedRect: insetRect, xRadius: 220, yRadius: 220)
outerBorder.lineWidth = 10
rgba(255, 255, 255, 0.12).setStroke()
outerBorder.stroke()

NSGraphicsContext.restoreGraphicsState()

guard let pngData = rep.representation(using: .png, properties: [:]) else {
	fputs("Failed to encode PNG data.\n", stderr)
	exit(1)
}

do {
	try FileManager.default.createDirectory(at: outputURL.deletingLastPathComponent(), withIntermediateDirectories: true)
	try pngData.write(to: outputURL)
} catch {
	fputs("Failed to write icon PNG: \(error)\n", stderr)
	exit(1)
}
