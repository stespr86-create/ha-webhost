// Wichtig: Alle Pfade sind RELATIV (kein führendes "/"), da Home Assistant
// Ingress die App unter einem dynamischen Prefix einbettet.

const sitesBody = document.getElementById("sites-body");
const statusMessage = document.getElementById("status-message");
const backupAllLink = document.getElementById("backup-all-link");
const settingsForm = document.getElementById("settings-form");
const publicBaseUrlInput = document.getElementById("public-base-url-input");

let publicBaseUrl = null;

const HTML_ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };

function escapeHtml(value) {
	return String(value).replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

function formatBytes(bytes) {
	if (bytes < 1024) return `${bytes} B`;
	if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
	return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function showStatus(message, isError = false) {
	statusMessage.textContent = message;
	statusMessage.className = "status" + (isError ? " error" : " success");
}

async function loadSites() {
	const res = await fetch("api/sites");
	const sites = await res.json();

	const hasActiveSite = sites.some((site) => site.status === "active");
	backupAllLink.classList.toggle("disabled", !hasActiveSite);
	backupAllLink.setAttribute("aria-disabled", String(!hasActiveSite));

	if (sites.length === 0) {
		sitesBody.innerHTML = '<tr><td colspan="5">Noch keine Sites vorhanden.</td></tr>';
		return;
	}

	sitesBody.innerHTML = sites
		.map((site) => {
			const url = `sites/${site.name}/`;
			const externalUrl = publicBaseUrl ? `${publicBaseUrl}/sites/${site.name}/` : null;
			const externalLinkHtml = externalUrl
				? `<a class="url-link" href="${escapeHtml(externalUrl)}" target="_blank" rel="noopener" title="${escapeHtml(externalUrl)}">🌐 ${escapeHtml(externalUrl)}</a>`
				: "";
			const wpInfo = site.source_type === "wordpress" && site.wordpress_admin_user
				? `<div style="font-size: 0.85em; color: #666; margin-top: 2px;">Admin: ${site.wordpress_admin_user}</div>`
				: "";
			return `
				<tr>
					<td>${site.name}${wpInfo}</td>
					<td>${site.source_type}</td>
					<td><span class="badge badge-${site.status}">${site.status}</span></td>
					<td>
						<a class="url-link" href="${url}" target="_blank" rel="noopener" title="${escapeHtml(url)}">🏠 ${url}</a>
						${externalLinkHtml}
					</td>
					<td>
						<button data-action="files" data-name="${site.name}">📂 Dateien</button>
						${site.source_type === "git" ? `<button data-action="redeploy" data-name="${site.name}">Redeploy</button>` : ""}
						${site.source_type === "upload" ? `<button data-action="redeploy-upload" data-name="${site.name}">🔄 Update</button>` : ""}
						${site.source_type === "gallery" ? `<button data-action="refresh-gallery" data-name="${site.name}" title="Holt die neueste Galerie-Oberfläche - Fotos bleiben erhalten">🔄 Seite aktualisieren</button>` : ""}
						<button data-action="delete" data-name="${site.name}" class="danger">Löschen</button>
					</td>
				</tr>
			`;
		})
		.join("");
}

sitesBody.addEventListener("click", async (event) => {
	const button = event.target.closest("button[data-action]");
	if (!button) return;

	const { action, name } = button.dataset;

	if (action === "delete") {
		if (!confirm(`Site "${name}" wirklich löschen? Alle Dateien gehen verloren.`)) return;
		const res = await fetch(`api/sites/${name}`, { method: "DELETE" });
		if (res.ok) {
			showStatus(`Site "${name}" gelöscht.`);
			loadSites();
		} else {
			const err = await res.json();
			showStatus(`Fehler: ${err.detail}`, true);
		}
	}

	if (action === "redeploy") {
		button.disabled = true;
		const res = await fetch(`api/sites/${name}/redeploy`, { method: "POST" });
		button.disabled = false;
		if (res.ok) {
			showStatus(`Site "${name}" neu deployt.`);
		} else {
			const err = await res.json();
			showStatus(`Fehler: ${err.detail}`, true);
		}
		loadSites();
	}

	if (action === "files") {
		openFileManager(name);
	}

	if (action === "refresh-gallery") {
		button.disabled = true;
		const res = await fetch(`api/sites/${name}/gallery/refresh`, { method: "POST" });
		button.disabled = false;
		if (res.ok) {
			showStatus(`Galerie-Seite "${name}" aktualisiert (Fotos bleiben erhalten).`);
		} else {
			const err = await res.json();
			showStatus(`Fehler: ${err.detail}`, true);
		}
	}

	if (action === "redeploy-upload") {
		redeployUploadTarget = name;
		redeployUploadInput.click();
	}
});

const redeployUploadInput = document.getElementById("redeploy-upload-input");
let redeployUploadTarget = null;

redeployUploadInput.addEventListener("change", async () => {
	const file = redeployUploadInput.files[0];
	const target = redeployUploadTarget;
	redeployUploadInput.value = "";
	redeployUploadTarget = null;
	if (!file || !target) return;

	const formData = new FormData();
	formData.append("name", target);
	formData.append("file", file);

	const res = await fetch("api/sites/upload", { method: "POST", body: formData });
	if (res.ok) {
		showStatus(`Site "${target}" aktualisiert.`);
	} else {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
	}
	loadSites();
});

document.getElementById("upload-form").addEventListener("submit", async (event) => {
	event.preventDefault();
	const form = event.target;
	const formData = new FormData(form);

	const res = await fetch("api/sites/upload", { method: "POST", body: formData });
	if (res.ok) {
		showStatus(`Site "${formData.get("name")}" erfolgreich deployt.`);
		form.reset();
		loadSites();
	} else {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
	}
});

document.getElementById("gallery-form").addEventListener("submit", async (event) => {
	event.preventDefault();
	const form = event.target;
	const formData = new FormData(form);

	const res = await fetch("api/sites/gallery", { method: "POST", body: formData });
	if (res.ok) {
		showStatus(`Galerie "${formData.get("name")}" angelegt.`);
		form.reset();
		loadSites();
	} else {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
	}
});

document.getElementById("git-form").addEventListener("submit", async (event) => {
	event.preventDefault();
	const form = event.target;
	const formData = new FormData(form);

	const res = await fetch("api/sites/git", { method: "POST", body: formData });
	if (res.ok) {
		showStatus(`Site "${formData.get("name")}" erfolgreich geklont und deployt.`);
		form.reset();
		loadSites();
	} else {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
	}
});

document.getElementById("wordpress-form").addEventListener("submit", async (event) => {
	event.preventDefault();
	const form = event.target;
	const formData = new FormData(form);
	const siteName = formData.get("name");
	const blogName = formData.get("blog_name") || "WordPress";
	const adminEmail = formData.get("admin_email") || "admin@example.com";

	const res = await fetch("api/sites/wordpress", { method: "POST", body: formData });
	if (res.ok) {
		const site = await res.json();
		const adminInfo = site.wordpress_admin_user ? ` Anmeldung: ${site.wordpress_admin_user} @ /sites/${siteName}/wp-login.php` : "";
		showStatus(`✅ WordPress-Site "${siteName}" erstellt.${adminInfo}`);
		form.reset();
		loadSites();
	} else {
		const err = await res.json();
		showStatus(`❌ Fehler: ${err.detail}`, true);
	}
});

backupAllLink.addEventListener("click", (event) => {
	if (backupAllLink.getAttribute("aria-disabled") === "true") {
		event.preventDefault();
	}
});

// Home Assistant registriert einen Service Worker fuer die eigene PWA, der
// (da wir same-origin im Ingress-Iframe laufen) auch unsere eigenen
// static/-Dateien zwischenspeichert - selbst nach einem Add-on-Update
// bekommt der Browser dann u.U. weiterhin die alte Version ausgeliefert.
// Dieser Knopf loescht gezielt nur die WebHost-eigenen Cache-Eintraege
// (nicht den gesamten HA-Cache) und laedt danach neu.
const clearCacheButton = document.getElementById("clear-cache-button");

clearCacheButton.addEventListener("click", async () => {
	if (!("caches" in window)) {
		showStatus("Cache-API in diesem Browser nicht verfügbar.", true);
		return;
	}

	clearCacheButton.disabled = true;
	let deleted = 0;
	try {
		const cacheNames = await caches.keys();
		for (const name of cacheNames) {
			const cache = await caches.open(name);
			const requests = await cache.keys();
			for (const req of requests) {
				if (req.url.includes("/static/")) {
					await cache.delete(req);
					deleted++;
				}
			}
		}
	} catch (err) {
		showStatus(`Fehler beim Cache-Leeren: ${err.message}`, true);
		clearCacheButton.disabled = false;
		return;
	}

	showStatus(`Cache geleert (${deleted} Einträge) – lade neu...`);
	setTimeout(() => window.location.reload(), 600);
});

async function loadSettings() {
	const res = await fetch("api/settings");
	const data = await res.json();
	publicBaseUrl = data.public_base_url;
	publicBaseUrlInput.value = publicBaseUrl || "";
}

settingsForm.addEventListener("submit", async (event) => {
	event.preventDefault();
	const value = publicBaseUrlInput.value.trim();

	const res = await fetch("api/settings", {
		method: "PUT",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ public_base_url: value || null }),
	});
	if (res.ok) {
		showStatus("Einstellungen gespeichert.");
		await loadSettings();
		loadSites();
	} else {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
	}
});

async function init() {
	await loadSettings();
	await loadSites();
}

init();
setInterval(loadSites, 10000);

// --- Datei-Manager ---

const fm = {
	siteName: null,
	path: "",
};

const fmOverlay = document.getElementById("file-manager-overlay");
const fmSiteNameEl = document.getElementById("fm-site-name");
const fmBreadcrumb = document.getElementById("fm-breadcrumb");
const fmUpButton = document.getElementById("fm-up");
const fmFileList = document.getElementById("fm-file-list");
const fmUploadInput = document.getElementById("fm-upload-input");
const fmMkdirForm = document.getElementById("fm-mkdir-form");
const fmMkdirName = document.getElementById("fm-mkdir-name");
const fmEditor = document.getElementById("fm-editor");
const fmEditorFilename = document.getElementById("fm-editor-filename");
const fmEditorContent = document.getElementById("fm-editor-content");

function fmJoin(path, name) {
	return path ? `${path}/${name}` : name;
}

function fmParent(path) {
	const parts = path.split("/").filter(Boolean);
	parts.pop();
	return parts.join("/");
}

async function openFileManager(siteName) {
	fm.siteName = siteName;
	fm.path = "";
	fmSiteNameEl.textContent = siteName;
	fmOverlay.hidden = false;
	fmEditor.hidden = true;
	await fmLoadList();
}

function closeFileManager() {
	fmOverlay.hidden = true;
	fm.siteName = null;
}

function fmRenderBreadcrumb() {
	fmBreadcrumb.textContent = "/" + fm.path;
	fmUpButton.disabled = fm.path === "";
}

async function fmLoadList() {
	const res = await fetch(`api/files/${fm.siteName}?path=${encodeURIComponent(fm.path)}`);
	if (!res.ok) {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
		return;
	}
	const data = await res.json();
	fmRenderBreadcrumb();

	if (data.entries.length === 0) {
		fmFileList.innerHTML = '<li class="fm-empty">Ordner ist leer.</li>';
		return;
	}

	fmFileList.innerHTML = data.entries
		.map((entry) => {
			const icon = entry.is_dir ? "📁" : "📄";
			const sizeLabel = entry.is_dir ? "" : `<span class="fm-size">${formatBytes(entry.size)}</span>`;
			const safeName = escapeHtml(entry.name);
			return `
				<li class="fm-entry" data-name="${safeName}" data-is-dir="${entry.is_dir}">
					<span class="fm-entry-name">${icon} ${safeName}</span>
					${sizeLabel}
					<button type="button" data-fm-action="delete" data-fm-name="${safeName}" class="danger fm-delete">🗑</button>
				</li>
			`;
		})
		.join("");
}

fmFileList.addEventListener("click", async (event) => {
	const deleteButton = event.target.closest("button[data-fm-action='delete']");
	if (deleteButton) {
		event.stopPropagation();
		const entryPath = fmJoin(fm.path, deleteButton.dataset.fmName);
		if (!confirm(`"${deleteButton.dataset.fmName}" wirklich löschen?`)) return;
		const res = await fetch(`api/files/${fm.siteName}?path=${encodeURIComponent(entryPath)}`, {
			method: "DELETE",
		});
		if (res.ok) {
			await fmLoadList();
		} else {
			const err = await res.json();
			showStatus(`Fehler: ${err.detail}`, true);
		}
		return;
	}

	const entry = event.target.closest("li.fm-entry");
	if (!entry) return;

	const { name, isDir } = entry.dataset;
	const entryPath = fmJoin(fm.path, name);

	if (entry.dataset.isDir === "true") {
		fm.path = entryPath;
		await fmLoadList();
	} else {
		await fmOpenFile(entryPath);
	}
});

fmUpButton.addEventListener("click", async () => {
	fm.path = fmParent(fm.path);
	await fmLoadList();
});

fmMkdirForm.addEventListener("submit", async (event) => {
	event.preventDefault();
	const name = fmMkdirName.value.trim();
	if (!name) return;
	const res = await fetch(`api/files/${fm.siteName}/mkdir?path=${encodeURIComponent(fmJoin(fm.path, name))}`, {
		method: "POST",
	});
	if (res.ok) {
		fmMkdirName.value = "";
		await fmLoadList();
	} else {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
	}
});

fmUploadInput.addEventListener("change", async () => {
	const file = fmUploadInput.files[0];
	if (!file) return;

	const formData = new FormData();
	formData.append("file", file);

	const res = await fetch(`api/files/${fm.siteName}/upload?path=${encodeURIComponent(fm.path)}`, {
		method: "POST",
		body: formData,
	});
	fmUploadInput.value = "";
	if (res.ok) {
		await fmLoadList();
	} else {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
	}
});

async function fmOpenFile(path) {
	const res = await fetch(`api/files/${fm.siteName}/content?path=${encodeURIComponent(path)}`);
	if (!res.ok) {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
		return;
	}
	const data = await res.json();
	fmEditor.dataset.path = path;
	fmEditorFilename.textContent = path;
	fmEditorContent.value = data.content;
	fmEditor.hidden = false;
}

document.getElementById("fm-editor-save").addEventListener("click", async () => {
	const path = fmEditor.dataset.path;
	const res = await fetch(`api/files/${fm.siteName}/content?path=${encodeURIComponent(path)}`, {
		method: "PUT",
		headers: { "Content-Type": "application/json" },
		body: JSON.stringify({ content: fmEditorContent.value }),
	});
	if (res.ok) {
		showStatus(`"${path}" gespeichert.`);
		fmEditor.hidden = true;
	} else {
		const err = await res.json();
		showStatus(`Fehler: ${err.detail}`, true);
	}
});

document.getElementById("fm-editor-cancel").addEventListener("click", () => {
	fmEditor.hidden = true;
});

document.getElementById("fm-close").addEventListener("click", closeFileManager);
fmOverlay.addEventListener("click", (event) => {
	if (event.target === fmOverlay) closeFileManager();
});
