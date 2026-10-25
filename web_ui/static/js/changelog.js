function changelogVersionLabel(markdown) {
    const match = String(markdown || "").match(/^##\s+(\d+\.\d+(?:\.\d+)?)(?:\s*\(([^)]+)\))?/m);
    if (!match) return "";
    const note = match[2] ? ` (${match[2].trim()})` : "";
    return `إصدار رقم ${match[1]}${note}`;
}

function paintAppVersion(markdown) {
    const label = changelogVersionLabel(markdown);
    if (!label) return;
    document.querySelectorAll("#appVersionLabel").forEach((node) => {
        node.textContent = label;
    });
}

function renderChangelog(markdown) {
    const body = document.getElementById("changelogBody");
    if (!body) return;
    if (window.marked && typeof marked.parse === "function") {
        body.innerHTML = marked.parse(markdown);
        return;
    }
    body.textContent = markdown;
}

async function loadChangelog() {
    const body = document.getElementById("changelogBody");
    if (body) body.textContent = "جارٍ فتح السجل…";
    const response = await fetch("/changes.md", { cache: "no-store" });
    if (!response.ok) throw new Error("changelog");
    const markdown = await response.text();
    paintAppVersion(markdown);
    renderChangelog(markdown);
}

function openChangelogModal() {
    const modal = document.getElementById("changelogModal");
    if (!modal) return;
    modal.classList.add("open");
    if (window.lucide) lucide.createIcons();
    loadChangelog().catch(() => {
        const body = document.getElementById("changelogBody");
        if (body) body.textContent = "تعذر فتح سجل الإصدارات.";
    });
}

function closeChangelogModal() {
    const modal = document.getElementById("changelogModal");
    if (modal) modal.classList.remove("open");
}

document.addEventListener("DOMContentLoaded", () => {
    loadChangelog().catch(() => {});
});
