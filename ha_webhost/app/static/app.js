// Wichtig: Alle Pfade sind RELATIV (kein führendes "/"), da Home Assistant
// Ingress die App unter einem dynamischen Prefix einbettet.

const sitesBody = document.getElementById("sites-body");
const statusMessage = document.getElementById("status-message");

function showStatus(message, isError = false) {
	statusMessage.textContent = message;
	statusMessage.className = "status" + (isError ? " error" : " success");
}

async function loadSites() {
	const res = await fetch("api/sites");
	const sites = await res.json();

	if (sites.length === 0) {
		sitesBody.innerHTML = '<tr><td colspan="5">Noch keine Sites vorhanden.</td></tr>';
		return;
	}

	sitesBody.innerHTML = sites
		.map((site) => {
			const url = `sites/${site.name}/`;
			return `
				<tr>
					<td>${site.name}</td>
					<td>${site.source_type}</td>
					<td><span class="badge badge-${site.status}">${site.status}</span></td>
					<td><a href="${url}" target="_blank" rel="noopener">${url}</a></td>
					<td>
						${site.source_type === "git" ? `<button data-action="redeploy" data-name="${site.name}">Redeploy</button>` : ""}
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

loadSites();
setInterval(loadSites, 10000);
