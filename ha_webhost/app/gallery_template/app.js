// Alle Pfade sind RELATIV (kein führendes "/"), damit die Seite sowohl
// ueber den Ingress- als auch den oeffentlichen Port unter beliebigem
// Prefix funktioniert.

(function () {
	"use strict";

	var POLL_INTERVAL_MS = 12000;

	var heroTitle = document.getElementById("hero-title");
	var eyebrow = document.getElementById("eyebrow");
	var externalLink = document.getElementById("external-link");
	var galleryGrid = document.getElementById("gallery-grid");
	var emptyState = document.getElementById("empty-state");
	var countLabel = document.getElementById("photo-count");
	var dropzone = document.getElementById("dropzone");
	var fileInput = document.getElementById("file-input");
	var captionInput = document.getElementById("caption-input");
	var uploadStatus = document.getElementById("upload-status");
	var lightbox = document.getElementById("lightbox");
	var lightboxMedia = document.getElementById("lightbox-media");
	var lightboxCaption = document.getElementById("lightbox-caption");
	var lightboxClose = document.getElementById("lightbox-close");
	var lightboxDownload = document.getElementById("lightbox-download");
	var lightboxPrev = document.getElementById("lightbox-prev");
	var lightboxNext = document.getElementById("lightbox-next");

	var ROTATIONS = [-4, 3, -2.5, 4, -3.5, 2, -1.5, 3.5];
	var currentPhotos = [];
	var currentIndex = -1;

	function escapeHtml(value) {
		return String(value).replace(/[&<>"']/g, function (ch) {
			return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
		});
	}

	function setUploadStatus(message, isError) {
		uploadStatus.textContent = message || "";
		uploadStatus.className = "upload-status" + (isError ? " error" : "");
	}

	function renderPhotos(photos) {
		currentPhotos = photos;
		countLabel.textContent = String(photos.length);
		emptyState.hidden = photos.length > 0;
		galleryGrid.innerHTML = photos
			.map(function (p, i) {
				var rot = ROTATIONS[i % ROTATIONS.length];
				var caption = p.caption || "Vom Fest";
				var src = "uploads/" + encodeURIComponent(p.filename);
				return (
					'<figure class="photo-card" style="--rot:' + rot + 'deg" data-index="' + i + '">' +
					'<div class="photo-frame"><img src="' + src + '" alt="' + escapeHtml(caption) + '" loading="lazy"></div>' +
					'<figcaption><span class="cap-text">' + escapeHtml(caption) + "</span></figcaption>" +
					'<a class="card-download" href="' + src + '" download="foto-' + (i + 1) + '.jpg" aria-label="Foto herunterladen">⬇ Herunterladen</a>' +
					"</figure>"
				);
			})
			.join("");
	}

	galleryGrid.addEventListener("click", function (e) {
		if (e.target.closest(".card-download")) return;
		var card = e.target.closest(".photo-card");
		if (!card) return;
		openLightbox(Number(card.dataset.index));
	});

	function showLightboxPhoto(index) {
		if (!currentPhotos.length) return;
		currentIndex = (index + currentPhotos.length) % currentPhotos.length;
		var photo = currentPhotos[currentIndex];
		var src = "uploads/" + encodeURIComponent(photo.filename);
		var caption = photo.caption || "Vom Fest";
		lightboxMedia.innerHTML = '<img src="' + src + '" alt="' + escapeHtml(caption) + '">';
		lightboxCaption.textContent = caption;
		lightboxDownload.href = src;
		lightboxDownload.download = "foto-" + (currentIndex + 1) + ".jpg";
		var hasMultiple = currentPhotos.length > 1;
		lightboxPrev.hidden = !hasMultiple;
		lightboxNext.hidden = !hasMultiple;
	}
	function openLightbox(index) {
		showLightboxPhoto(index);
		lightbox.hidden = false;
		requestAnimationFrame(function () { lightbox.classList.add("open"); });
	}
	function closeLightbox() {
		lightbox.classList.remove("open");
		setTimeout(function () { lightbox.hidden = true; }, 180);
	}
	lightboxClose.addEventListener("click", closeLightbox);
	lightboxPrev.addEventListener("click", function () { showLightboxPhoto(currentIndex - 1); });
	lightboxNext.addEventListener("click", function () { showLightboxPhoto(currentIndex + 1); });
	lightbox.addEventListener("click", function (e) { if (e.target === lightbox) closeLightbox(); });
	document.addEventListener("keydown", function (e) {
		if (lightbox.hidden) return;
		if (e.key === "Escape") closeLightbox();
		if (e.key === "ArrowLeft") showLightboxPhoto(currentIndex - 1);
		if (e.key === "ArrowRight") showLightboxPhoto(currentIndex + 1);
	});

	async function loadMeta(applyHeader) {
		try {
			var res = await fetch("api/meta", { cache: "no-store" });
			if (!res.ok) return;
			var data = await res.json();
			if (applyHeader) {
				document.title = data.title;
				heroTitle.textContent = data.title;
				eyebrow.textContent = data.title;
				if (data.link_url) {
					externalLink.href = data.link_url;
					externalLink.textContent = (data.link_label || "Weitere Fotos ansehen") + " ↗";
					externalLink.hidden = false;
				}
			}
			renderPhotos(data.photos || []);
		} catch (err) {
			/* Netzwerkfehler beim Poll - naechster Versuch folgt automatisch */
		}
	}

	function resizeForUpload(file, maxDim) {
		return new Promise(function (resolve, reject) {
			var reader = new FileReader();
			reader.onload = function () {
				var img = new Image();
				img.onload = function () {
					var width = img.width, height = img.height;
					if (width > maxDim || height > maxDim) {
						if (width > height) { height = Math.round(height * maxDim / width); width = maxDim; }
						else { width = Math.round(width * maxDim / height); height = maxDim; }
					}
					var canvas = document.createElement("canvas");
					canvas.width = width; canvas.height = height;
					canvas.getContext("2d").drawImage(img, 0, 0, width, height);
					canvas.toBlob(function (blob) { resolve(blob); }, "image/jpeg", 0.85);
				};
				img.onerror = reject;
				img.src = reader.result;
			};
			reader.onerror = reject;
			reader.readAsDataURL(file);
		});
	}

	async function handleFiles(fileList) {
		var files = Array.prototype.filter.call(fileList, function (f) { return f.type.indexOf("image/") === 0; });
		if (!files.length) return;
		var caption = captionInput.value.trim();

		for (var i = 0; i < files.length; i++) {
			setUploadStatus("Lade „" + files[i].name + "“ hoch …");
			try {
				var blob = await resizeForUpload(files[i], 1600);
				var formData = new FormData();
				formData.append("file", blob, "foto.jpg");
				formData.append("caption", caption);
				var res = await fetch("api/upload", { method: "POST", body: formData });
				if (!res.ok) {
					var err = await res.json().catch(function () { return {}; });
					setUploadStatus(err.detail || "Upload fehlgeschlagen.", true);
					continue;
				}
			} catch (err) {
				setUploadStatus("Upload fehlgeschlagen (" + files[i].name + ").", true);
				continue;
			}
		}
		setUploadStatus("Fertig – danke fürs Teilen!");
		captionInput.value = "";
		loadMeta(false);
	}

	dropzone.addEventListener("click", function () { fileInput.click(); });
	dropzone.addEventListener("keydown", function (e) {
		if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
	});
	fileInput.addEventListener("change", function () {
		if (fileInput.files.length) handleFiles(fileInput.files);
		fileInput.value = "";
	});
	["dragenter", "dragover"].forEach(function (evt) {
		dropzone.addEventListener(evt, function (e) { e.preventDefault(); dropzone.classList.add("dragging"); });
	});
	["dragleave", "drop"].forEach(function (evt) {
		dropzone.addEventListener(evt, function (e) { e.preventDefault(); dropzone.classList.remove("dragging"); });
	});
	dropzone.addEventListener("drop", function (e) {
		if (e.dataTransfer && e.dataTransfer.files.length) handleFiles(e.dataTransfer.files);
	});

	loadMeta(true);
	setInterval(function () { loadMeta(false); }, POLL_INTERVAL_MS);

	var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
	if (!reduceMotion) {
		var canvas = document.getElementById("confetti-canvas");
		var ctx2 = canvas.getContext("2d");
		var hero = document.getElementById("hero");

		function sizeCanvas() {
			var rect = hero.getBoundingClientRect();
			canvas.width = rect.width;
			canvas.height = rect.height;
		}
		sizeCanvas();
		window.addEventListener("resize", sizeCanvas);

		var colors = ["#FF6B5B", "#2EC4B6", "#FFC94D", "#FF9F80"];
		var pieces = [];
		for (var n = 0; n < 70; n++) {
			pieces.push({
				x: Math.random() * canvas.width,
				y: -20 - Math.random() * canvas.height * 0.6,
				size: 5 + Math.random() * 6,
				color: colors[Math.floor(Math.random() * colors.length)],
				speedY: 1.4 + Math.random() * 2.3,
				speedX: (Math.random() - 0.5) * 1.4,
				rot: Math.random() * 360,
				rotSpeed: (Math.random() - 0.5) * 8
			});
		}
		var start = null;
		function frame(ts) {
			if (!start) start = ts;
			var elapsed = ts - start;
			ctx2.clearRect(0, 0, canvas.width, canvas.height);
			pieces.forEach(function (p) {
				p.x += p.speedX; p.y += p.speedY; p.rot += p.rotSpeed;
				ctx2.save();
				ctx2.translate(p.x, p.y);
				ctx2.rotate((p.rot * Math.PI) / 180);
				ctx2.fillStyle = p.color;
				ctx2.fillRect(-p.size / 2, -p.size / 3, p.size, p.size * 0.6);
				ctx2.restore();
			});
			if (elapsed < 2600) {
				requestAnimationFrame(frame);
			} else {
				ctx2.clearRect(0, 0, canvas.width, canvas.height);
			}
		}
		requestAnimationFrame(frame);
	}
})();
