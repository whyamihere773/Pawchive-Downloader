.pragma library

function listContentRatio(contentH, count, rowEstimate, viewH) {
    var effectiveH = contentH || 0
    if (typeof count === "number" && count > 0) {
        effectiveH = Math.max(effectiveH, count * rowEstimate)
    }
    return Math.max(1.0, effectiveH / Math.max(1, viewH))
}

function gridContentRatio(contentH, count, cellW, cellH, viewW, viewH) {
    var effectiveH = contentH || 0
    if (typeof count === "number" && count > 0 && cellW > 0 && cellH > 0 && viewW > 0) {
        var cols = Math.max(1, Math.floor(viewW / cellW))
        var rows = Math.ceil(count / cols)
        effectiveH = Math.max(effectiveH, rows * cellH)
    }
    return Math.max(1.0, effectiveH / Math.max(1, viewH))
}

function flickDecel(ratio) {
    return Math.max(4800, 6000 - Math.min(1200, Math.max(0.0, (ratio || 1.0) - 1.0) * 40))
}

function maxFlickVel(ratio) {
    return Math.min(7500, 3200 + Math.min(4300, Math.max(0.0, (ratio || 1.0) - 1.0) * 120))
}

function stepWheelMomentum(flickItem, delta, maxMomentum) {
    var now = Date.now()
    var dt = now - (flickItem._lastWheelTime || 0)
    var dir = delta > 0 ? 1 : -1
    var prevDir = flickItem._lastWheelDir || 0
    flickItem._lastWheelTime = now
    flickItem._lastWheelDir = dir

    // Calm baseline on first notch or direction change; accelerate cleanly as the user keeps scrolling.
    if (dt < 260 && dir === prevDir) {
        var streak = (flickItem._scrollStreak || 0) + Math.min(2.0, Math.abs(delta) / 120.0)
        flickItem._scrollStreak = streak
        flickItem._wheelMomentum = Math.min(maxMomentum || 3.0, 1.0 + Math.sqrt(streak) * 0.42)
    } else {
        flickItem._scrollStreak = 0
        flickItem._wheelMomentum = 1.0
    }
    return flickItem._wheelMomentum
}

function applyWheelFlick(flickItem, delta) {
    if (!flickItem || delta === 0) return false
    var maxY = Math.max(0, (flickItem.contentHeight || 0) - (flickItem.height || 0))
    if (maxY <= 0.5) return false

    var momentum = stepWheelMomentum(flickItem, delta, 3.0)
    var notchV = (delta / 120.0) * (1100 * momentum)

    // In Qt Flickable, flick(0, v) drives verticalVelocity toward -v (d(contentY)/dt = -v).
    var curFlickV = flickItem.flicking ? -flickItem.verticalVelocity : 0
    var targetV = notchV
    if ((notchV > 0 && curFlickV > 0) || (notchV < 0 && curFlickV < 0)) {
        var streak = flickItem._scrollStreak || 0
        var carryFactor = streak > 0 ? Math.min(0.48, 0.30 + Math.sqrt(streak) * 0.06) : 0.30
        targetV = curFlickV * carryFactor + notchV
    }
    var cap = flickItem.maximumFlickVelocity || 5000
    targetV = Math.max(-cap, Math.min(cap, targetV))
    flickItem.flick(0, targetV)
    return true
}
