// Fading curve for an ND2 time-lapse.
// Opens the ND2 with Bio-Formats (virtual stack), makes a max-intensity projection over Z for every
// time point, measures the brightness of each projected frame, saves a CSV, a plot and the projection
// into a "<file>_fiji" folder next to the ND2.
//
// Use: Fiji > Plugins > Macros > Run... > pick this file, then pick the .nd2 file.
// For large files set Edit > Options > Memory & Threads high enough first.
// The macro argument "file=<path.nd2> out=<folder> interval=<minutes>" is also accepted (not tested headless).
//
// Brightness metrics per time point (on the max projection):
//   mean_all    = mean of the whole frame
//   p99_9       = 99.9th percentile (the brightest nuclei; comparable across time)
//   max         = single brightest pixel (noisy)

arg = getArgument();
file = ""; out = ""; interval = 1;
if (arg != "") {
    parts = split(arg, " ");
    for (i = 0; i < parts.length; i++) {
        kv = split(parts[i], "=");
        if (kv[0] == "file") file = kv[1];
        if (kv[0] == "out") out = kv[1];
        if (kv[0] == "interval") interval = parseFloat(kv[1]);
    }
    setBatchMode(true);
} else {
    file = File.openDialog("Choose the ND2 time-lapse");
    Dialog.create("Fading curve");
    Dialog.addNumber("Interval between time points (min):", 1);
    Dialog.show();
    interval = Dialog.getNumber();
}
if (out == "") out = File.getParent(file) + File.separator + File.nameWithoutExtension + "_fiji";
File.makeDirectory(out);
name = File.getNameWithoutExtension(file);

run("Bio-Formats Importer", "open=[" + file + "] color_mode=Default view=Hyperstack stack_order=XYCZT use_virtual_stack");
src = getTitle();
Stack.getDimensions(w, h, channels, slices, frames);
print("Opened " + src + ": " + w + "x" + h + ", Z=" + slices + ", T=" + frames);

if (slices > 1) {
    run("Z Project...", "projection=[Max Intensity] all");
} else {
    run("Duplicate...", "duplicate");
}
proj = getTitle();
selectWindow(src); close();
selectWindow(proj);
n = nSlices;

run("Clear Results");
tmin = newArray(n); p999 = newArray(n);
for (t = 1; t <= n; t++) {
    setSlice(t);
    getStatistics(area, mean, min, max);
    getHistogram(values, counts, 4096, 0, 4096);
    total = 0; for (k = 0; k < counts.length; k++) total += counts[k];
    target = total * 0.999; acc = 0; pct = max;
    for (k = 0; k < counts.length; k++) { acc += counts[k]; if (acc >= target) { pct = values[k]; k = counts.length; } }
    tmin[t-1] = (t - 1) * interval; p999[t-1] = pct;
    setResult("time_point", t-1, t-1);
    setResult("t_min", t-1, tmin[t-1]);
    setResult("mean_all", t-1, mean);
    setResult("p99_9", t-1, pct);
    setResult("max", t-1, max);
}
updateResults();
saveAs("Results", out + File.separator + name + "_fading_curve.csv");

Plot.create("Fading curve - " + name, "time (min)", "99.9th percentile intensity (max projection)", tmin, p999);
Plot.setStyle(0, "blue,none,1.5,Line");
Plot.addText("REHEARSAL data - first: " + p999[0] + "   last: " + p999[n-1] + "   (" + d2s(100 * p999[n-1] / p999[0], 1) + "%)", 0.02, 0.08);
Plot.show();
saveAs("PNG", out + File.separator + name + "_fading_curve.png");

selectWindow(proj);
saveAs("Tiff", out + File.separator + name + "_maxproj.tif");
print("Saved to " + out);
print("first p99.9 = " + p999[0] + ", last = " + p999[n-1] + " (" + d2s(100 * p999[n-1] / p999[0], 1) + "% of first)");
