/**
 * ITSC Traffic Control Center Custom Canvas Charts
 * Lightweight, dependency-free chart drawer using HTML5 Canvas
 */

function drawBarChart(canvasId, dataset, labels, accentColor) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    // Scale canvas resolution based on display dimensions
    const container = canvas.parentNode;
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Dimensions parameters
    const padLeft = 40;
    const padRight = 20;
    const padTop = 20;
    const padBottom = 25;

    const plotWidth = width - padLeft - padRight;
    const plotHeight = height - padTop - padBottom;

    ctx.clearRect(0, 0, width, height);

    // Draw background vertical metrics helper lines (grid)
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    const gridLines = 4;
    for (let i = 0; i <= gridLines; i++) {
        const y = padTop + (plotHeight / gridLines) * i;
        ctx.beginPath();
        ctx.moveTo(padLeft, y);
        ctx.lineTo(width - padRight, y);
        ctx.stroke();
    }

    // Determine max value scale
    const maxVal = Math.max(...dataset, 10);

    // Draw Bars
    const spacing = plotWidth / dataset.length;
    const barWidth = spacing * 0.45;

    dataset.forEach((val, index) => {
        const barHeight = (val / maxVal) * plotHeight;
        const x = padLeft + (spacing * index) + (spacing - barWidth) / 2;
        const y = padTop + plotHeight - barHeight;

        // Apply cyber glow shadow settings
        ctx.shadowColor = accentColor;
        ctx.shadowBlur = 10;

        // Gradient styling
        const gradient = ctx.createLinearGradient(x, y, x, y + barHeight);
        gradient.addColorStop(0, accentColor);
        gradient.addColorStop(1, 'rgba(0, 114, 255, 0.05)');

        ctx.fillStyle = gradient;
        
        // Rounded bar corners path
        const radius = 4;
        ctx.beginPath();
        ctx.moveTo(x, y + barHeight);
        ctx.lineTo(x, y + radius);
        ctx.quadraticCurveTo(x, y, x + radius, y);
        ctx.lineTo(x + barWidth - radius, y);
        ctx.quadraticCurveTo(x + barWidth, y, x + barWidth, y + radius);
        ctx.lineTo(x + barWidth, y + barHeight);
        ctx.closePath();
        ctx.fill();

        // Reset glow shadow
        ctx.shadowBlur = 0;

        // Draw axis/value texts
        ctx.fillStyle = '#8fa0dd';
        ctx.font = '10px "Rajdhani", sans-serif';
        ctx.textAlign = 'center';
        
        // Value atop the bar
        ctx.fillStyle = '#ffffff';
        ctx.fillText(val === 0 ? '--' : val, x + barWidth / 2, y - 6);
        
        // Label bottom axis
        ctx.fillStyle = '#8fa0dd';
        ctx.fillText(labels[index], x + barWidth / 2, height - 6);
    });
}

// Initial draw logic loading
window.addEventListener('DOMContentLoaded', () => {
    // Initial states: Zero values for dashboard (mocking "--" state)
    drawBarChart('dashboardChart', [0, 0, 0, 0], ['ROAD 1', 'ROAD 2', 'ROAD 3', 'ROAD 4'], '#00f0ff');
    
    // Performance reports page loads with simulated historical stats
    drawBarChart('reportsChart', [45, 78, 30, 62], ['ROAD 1', 'ROAD 2', 'ROAD 3', 'ROAD 4'], '#0072ff');
});

// Keep canvas responsive across resize events
window.addEventListener('resize', () => {
    drawBarChart('dashboardChart', [0, 0, 0, 0], ['ROAD 1', 'ROAD 2', 'ROAD 3', 'ROAD 4'], '#00f0ff');
    drawBarChart('reportsChart', [45, 78, 30, 62], ['ROAD 1', 'ROAD 2', 'ROAD 3', 'ROAD 4'], '#0072ff');
});
