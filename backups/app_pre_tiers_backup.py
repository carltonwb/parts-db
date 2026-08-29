import sqlite3, io, csv, os, shutil
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, render_template_string, request, redirect, Response, send_from_directory, send_file, jsonify
from werkzeug.utils import secure_filename

app = Flask(__name__)
DB_FILE = "/opt/parts-db/inventory.db"
UPLOAD_FOLDER = "/opt/parts-db/images"
BACKUP_FOLDER = "/opt/parts-db/backups"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

def get_phoenix_time():
    return datetime.now(ZoneInfo("America/Phoenix")).strftime("%Y-%m-%d %H:%M:%S")

def init_db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("CREATE TABLE IF NOT EXISTS inventory (id INTEGER PRIMARY KEY AUTOINCREMENT, location TEXT NOT NULL, part_name TEXT NOT NULL, category TEXT, quantity INTEGER DEFAULT 0, notes TEXT, purchase_url TEXT, image_filename TEXT, last_updated TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM categories")
    if cursor.fetchone() == 0:
        for d in ["Fasteners", "Passive Electronics", "Active Electronics", "Hardware", "Empty Bin"]:
            try: conn.execute("INSERT INTO categories (name) VALUES (?)", (d,))
            except: pass
    conn.commit()
    conn.close()

HTML_PAGE = """<!DOCTYPE html>
<html>
<head>
    <title>Inventory</title>
    <style>
        body { font-family: sans-serif; max-width: 1050px; margin: 30px auto; padding: 0 15px; background: #f4f4f4; color: #333; margin-bottom: 100px; }
        .box { background: white; padding: 20px; border-radius: 5px; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        input, select { padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; font-size: 14px; }
        button { padding: 8px 15px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold; }
        .s-btn { background: #007bff; }
        .e-btn { background: #17a2b8; color: white; text-decoration: none; padding: 6px 12px; float: right; border-radius: 4px; font-size: 13px; margin-left: 5px; font-weight: bold; }
        .box-btn { background: #6f42c1; }
        .r-btn { background: #fd7e14; }
        .db-btn { background: #343a40; }
        .del-btn { background: #dc3545; padding: 4px 8px; font-size: 12px; margin: 0; }
        .save-btn { background: #28a745; padding: 4px 8px; font-size: 12px; margin: 0; }
        .edit-lnk { color: #007bff; text-decoration: none; font-size: 13px; font-weight: bold; margin-right: 10px; }
        .qty-btn { background: #6c757d; padding: 2px 6px; font-size: 12px; font-weight: bold; border-radius: 3px; display: inline-block; text-decoration: none; color: white; margin: 0 2px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; background: white; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 14px; vertical-align: middle; }
        th { background: #eee; }
        .row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; }
        .row2 { display: grid; grid-template-columns: 2fr 1fr; gap: 8px; }
        .time-text { font-size: 11px; color: #666; font-family: monospace; }
        .t-input { padding: 4px; margin: 0; font-size: 13px; }
        .part-img { max-width: 60px; max-height: 60px; border-radius: 4px; border: 1px solid #ccc; display: block; object-fit: cover; }
        .buy-link { color: #28a745; text-decoration: none; font-weight: bold; font-size: 13px; }
        .drop-zone { border: 2px dashed #999; padding: 12px; text-align: center; background: #fdfdfd; border-radius: 4px; cursor: pointer; margin-top: 5px; }
        .drop-zone--over { border-color: #007bff; background: #e6f0fa; }
        .drop-zone__input { display: none; }
        .drop-zone__prompt { font-size: 13px; color: #555; font-weight: bold; }
        .modal { display: none; position: fixed; z-index: 10000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.5); }
        .modal-content { background-color: #fff; margin: 5% auto; padding: 20px; border-radius: 5px; width: 70%; max-width: 800px; box-shadow: 0 4px 8px rgba(0,0,0,0.2); }
        .close-btn { color: #aaa; float: right; font-size: 24px; font-weight: bold; cursor: pointer; }
        .close-btn:hover { color: #000; }
        .img-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: 12px; margin-top: 15px; max-height: 300px; overflow-y: auto; padding: 5px; border: 1px solid #eee; }
        .grid-card { border: 1px solid #ddd; border-radius: 4px; padding: 5px; text-align: center; cursor: pointer; background: #fafafa; transition: transform 0.1s ease; }
        .grid-card:hover { border-color: #007bff; background: #eaf4ff; transform: scale(1.03); }
        .grid-card img { width: 90px; height: 90px; object-fit: cover; border-radius: 3px; }
        .grid-card div { font-size: 11px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; margin-top: 4px; color: #555; }
        .media-link { display: inline-block; font-size: 12px; color: #007bff; text-decoration: none; margin-top: 5px; cursor: pointer; font-weight: bold; }
        .bulk-bar { display: none; position: fixed; bottom: 0; left: 0; width: 100%; background: #343a40; color: white; padding: 15px 20px; box-shadow: 0 -4px 10px rgba(0,0,0,0.2); z-index: 9999; box-sizing: border-box; }
        .bulk-content { max-width: 1050px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; }
        .bulk-actions button { margin-left: 10px; padding: 8px 16px; font-size: 13px; }
        .b-chk { transform: scale(1.3); cursor: pointer; }
    </style>
"""
HTML_PAGE += """
    <script>
        let activeTargetInputId = null;
        let activePreviewContainerId = null;

        function setMode(mode){
            document.getElementById("d_row").style.display = mode === "drawer" ? "grid" : "none";
            document.getElementById("s_row").style.display = mode === "shelf" ? "block" : "none";
        }
        function setBulkMode(mode){
            document.getElementById("bulk_d_row").style.display = mode === "drawer" ? "grid" : "none";
            document.getElementById("bulk_s_row").style.display = mode === "shelf" ? "block" : "none";
        }

        function saveSelection() {
            const checkedBoxes = document.querySelectorAll('.item-chk:checked');
            const savedIds = Array.from(checkedBoxes).map(chk => chk.value);
            localStorage.setItem('selected_inventory_ids', JSON.stringify(savedIds));
        }

        function loadSelection() {
            const savedData = localStorage.getItem('selected_inventory_ids');
            if (!savedData) return;
            const savedIds = JSON.parse(savedData);
            
            const checkboxes = document.querySelectorAll('.item-chk');
            checkboxes.forEach(chk => {
                if (savedIds.includes(chk.value)) {
                    chk.checked = true;
                }
            });
            updateBulkBar();
        }

        function clearSelection() {
            localStorage.removeItem('selected_inventory_ids');
            const checkboxes = document.querySelectorAll('.item-chk');
            checkboxes.forEach(chk => chk.checked = false);
            const master = document.querySelector('.b-chk');
            if(master) master.checked = false;
            updateBulkBar();
        }

        function saveScrollPosition() {
            localStorage.setItem('inventory_scroll_y', window.scrollY);
        }

        function updateStickyControls() {
            const form = document.getElementById("filterForm");
            sessionStorage.setItem("sticky_q", form.q.value);
            sessionStorage.setItem("sticky_cat", form.filter_cat.value);
            sessionStorage.setItem("sticky_loc_type", form.filter_loc_type.value);
            sessionStorage.setItem("sticky_sort", form.sort.value);
            saveScrollPosition();
            form.submit();
        }

        function handleFormSubmit(formEl) {
            saveScrollPosition();
            const controls = ["q", "filter_cat", "filter_loc_type", "sort"];
            controls.forEach(param => {
                let val = sessionStorage.getItem("sticky_" + param) || "";
                let hiddenInput = document.createElement("input");
                hiddenInput.type = "hidden";
                hiddenInput.name = param;
                hiddenInput.value = val;
                formEl.appendChild(hiddenInput);
            });
        }

        document.addEventListener("DOMContentLoaded", () => {
            loadSelection();

            const savedScrollY = localStorage.getItem('inventory_scroll_y');
            if (savedScrollY !== null) {
                window.scrollTo(0, parseInt(savedScrollY));
                localStorage.removeItem('inventory_scroll_y');
            }

            const dropZone = document.getElementById("image-drop-zone");
            const fileInput = document.getElementById("part_image_input");
            if (dropZone && fileInput) {
                dropZone.addEventListener("click", () => fileInput.click());
                
                fileInput.addEventListener("change", () => {
                    if(fileInput.files.length) updatePrompt(dropZone, fileInput.files[0].name);
                });
                
                dropZone.addEventListener("dragover", (e) => { e.preventDefault(); dropZone.classList.add("drop-zone--over"); });
                ["dragleave", "dragend"].forEach(type => {
                    dropZone.addEventListener(type, () => dropZone.classList.remove("drop-zone--over"));
                });
                
                dropZone.addEventListener("drop", (e) => {
                    e.preventDefault();
                    dropZone.classList.remove("drop-zone--over");
                    if (e.dataTransfer.files.length) {
                        fileInput.files = e.dataTransfer.files;
                        updatePrompt(dropZone, e.dataTransfer.files[0].name);
                    }
                });
            }
        });

        function updatePrompt(zone, name) { zone.querySelector(".drop-zone__prompt").textContent = "Selected: " + name; }
        
        function openImageGallery(inputId, previewId) {
            activeTargetInputId = inputId;
            activePreviewContainerId = previewId;
            document.getElementById("galleryModal").style.display = "block";
            fetch('/api/existing_images')
                .then(res => res.json())
                .then(images => {
                    const grid = document.getElementById("modalGrid");
                    grid.innerHTML = images.length === 0 ? '<p style="grid-column:1/-1;text-align:center;color:#777;padding:20px;">No images found.</p>' : '';
                    images.forEach(img => {
                        const card = document.createElement("div");
                        card.className = "grid-card";
                        card.onclick = () => selectImage(img);
                        card.innerHTML = '<img src="/images/' + img + '"><div>' + img + '</div>';
                        grid.appendChild(card);
                    });
                });
        }
        function closeGallery() { document.getElementById("galleryModal").style.display = "none"; }
        
        function selectImage(filename) {
            if(activeTargetInputId) document.getElementById(activeTargetInputId).value = filename;
            if(activePreviewContainerId) {
                document.getElementById(activePreviewContainerId).innerHTML = '<img src="/images/' + filename + '" style="max-width:60px; max-height:60px; border-radius:4px;"><br><span style="font-size:11px;color:#28a745;">Selected: ' + filename + '</span>';
            }
            closeGallery();
        }
        
        function toggleSelectAll(master) {
            const checkboxes = document.querySelectorAll('.item-chk');
            checkboxes.forEach(chk => chk.checked = master.checked);
            saveSelection();
            updateBulkBar();
        }
        
        function updateBulkBar() {
            const selected = document.querySelectorAll('.item-chk:checked');
            const bar = document.getElementById('bulkActionBar');
            const countLabel = document.getElementById('bulkCountLabel');
            if (selected.length > 0) {
                countLabel.textContent = selected.length + " items selected";
                bar.style.display = "block";
            } else {
                bar.style.display = "none";
            }
        }
        
        function triggerBulkEdit() {
            const selected = document.querySelectorAll('.item-chk:checked');
            let ids = [];
            selected.forEach(chk => ids.push(chk.value));
            document.getElementById('bulk_ids_input').value = ids.join(',');
            document.getElementById('bulkEditModal').style.display = "block";
        }
        function closeBulkModal() { document.getElementById('bulkEditModal').style.display = "none"; }
    </script>
</head>
"""
HTML_PAGE += """
<body>
    <h2>🔩 Workshop Inventory Engine</h2>
    <div id="galleryModal" class="modal">
        <div class="modal-content">
            <span class="close-btn" onclick="closeGallery()">&times;</span>
            <h3 style="margin-top:0;">📋 Select An Image From Database Gallery</h3>
            <div id="modalGrid" class="img-grid"></div>
        </div>
    </div>
    <div id="bulkEditModal" class="modal">
        <div class="modal-content" style="max-width:550px;">
            <span class="close-btn" onclick="closeBulkModal()">&times;</span>
            <h3 style="margin-top:0; color:#6f42c1;">⚙️ Bulk Modify Selected Inventory Rows</h3>
            <form action="/bulk_update" method="POST" onsubmit="handleFormSubmit(this);">
                <input type="hidden" name="bulk_ids" id="bulk_ids_input" value="">
                <p style="font-size:12px; color:#666; margin-bottom:15px;">Leave fields completely empty or set to 'Unchanged' if you do not want to alter their current values.</p>
                <label><b>Update Location Mode</b></label>
                <div style="margin-bottom:10px; margin-top:5px;">
                    <input type="radio" name="bulk_loc_type" value="unchanged" checked onclick="setBulkMode('unchanged')" style="width:auto;"> <b>Leave Location Unchanged</b> &nbsp;&nbsp;
                    <input type="radio" name="bulk_loc_type" value="drawer" onclick="setBulkMode('drawer')" style="width:auto;"> <b>Drawer Mode</b> &nbsp;&nbsp;
                    <input type="radio" name="bulk_loc_type" value="shelf" onclick="setBulkMode('shelf')" style="width:auto;"> <b>Shelf Mode</b> &nbsp;&nbsp;
                    <input type="radio" name="bulk_loc_type" value="unassigned" onclick="setBulkMode('unassigned')" style="width:auto;"> <b style="color:#007bff;">Unassigned Mode</b>
                </div>
                <div id="bulk_d_row" class="row3" style="display:none; margin-bottom:10px;">
                    <select name="bulk_drawer">{% for d in range(1, 36) %}<option value="D{{ d }}">Drawer {{ d }}</option>{% endfor %}</select>
                    <select name="bulk_row_letter">{% for r in ['A','B','C','D','E','F','G','H'] %}<option value="{{ r }}">Row {{ r }}</option>{% endfor %}</select>
                    <select name="bulk_col_num">{% for c in range(1, 10) %}<option value="{{ c }}">Col {{ c }}</option>{% endfor %}</select>
                </div>
                <div id="bulk_s_row" style="display:none; margin-bottom:10px;">
                    <input type="text" name="bulk_shelf_name" placeholder="Type custom location name (e.g., SHELF-A, BACK-WALL)">
                </div>
                <label><b>Change Category / Item Type</b></label>
                <select name="bulk_category">
                    <option value="">-- Leave Unchanged --</option>
                    {% for cat in categories %}<option value="{{ cat }}">{{ cat }}</option>{% endfor %}</select>
                <label style="display:block; margin-top:10px;"><b>Assign Synchronized Picture Asset</b></label>
                <input type="hidden" name="bulk_image_filename" id="bulk_target_img_filename" value="">
                <div id="bulk_img_preview" style="margin:5px 0;"></div>
                <a class="media-link" onclick="openImageGallery('bulk_target_img_filename', 'bulk_img_preview')">📋 Browse Existing Images Container Gallery</a>
                <div style="margin-top:20px; text-align:right;">
                    <button type="button" onclick="closeBulkModal()" style="background:#6c757d; margin-right:5px;">Cancel</button>
                    <button type="submit" style="background:#6f42c1;">Apply Bulk Updates</button>
                </div>
            </form>
        </div>
    </div>
    <div class="box">
        <h3>Add New Part Manually</h3>
        <form action="/add" method="POST" enctype="multipart/form-data" onsubmit="handleFormSubmit(this);">
            <input type="hidden" name="existing_image_filename" id="manual_existing_image" value="">
            <div style="margin-bottom:10px;">
                <input type="radio" name="loc_type" value="unassigned" checked onclick="setMode('unassigned')" style="width:auto;"> <b style="color:#007bff;">Unassigned Mode</b> &nbsp;&nbsp;
                <input type="radio" name="loc_type" value="drawer" onclick="setMode('drawer')" style="width:auto;"> <b>Drawer Mode (1-35)</b> &nbsp;&nbsp;
                <input type="radio" name="loc_type" value="shelf" onclick="setMode('shelf')" style="width:auto;"> <b>Freeform Shelf Mode</b>
            </div>
            <div id="d_row" class="row3" style="display:none;">
                <select name="drawer">{% for d in range(1, 36) %}<option value="D{{ d }}">Drawer {{ d }}</option>{% endfor %}</select>
                <select name="row_letter">{% for r in ['A','B','C','D','E','F','G','H'] %}<option value="{{ r }}">Row {{ r }}</option>{% endfor %}</select>
                <select name="col_num">{% for c in range(1, 10) %}<option value="{{ c }}">Col {{ c }}</option>{% endfor %}</select>
            </div>
            <div id="s_row" style="display:none;">
                <input type="text" name="shelf_name" placeholder="Type custom location name (e.g., SHELF-A, BACK-WALL, WORKBENCH)">
            </div>
            <div class="row2" style="margin-top:10px;">
                <input type="text" name="part_name" placeholder="Part Name" required>
                <select name="category">
                    {% for cat in categories %}<option value="{{ cat }}">{{ cat }}</option>{% endfor %}</select>
            </div>
            <div class="row2">
                <input type="text" name="purchase_url" placeholder="Paste Purchase Link URL (optional)">
                <input type="number" name="quantity" value="0">
            </div>
            <div class="row2">
                <input type="text" name="notes" placeholder="Notes (optional)">
                <div>
                    <div id="image-drop-zone" class="drop-zone">
                        <span class="drop-zone__prompt">Drag & Drop Image Here or Click to Browse</span>
                        <input type="file" name="part_image" id="part_image_input" class="drop-zone__input" accept="image/*">
                    </div>
                    <div id="manual_preview_target" style="margin-top:5px; text-align:center;"></div>
                    <center><a class="media-link" onclick="openImageGallery('manual_existing_image', 'manual_preview_target')">📋 Choose Picture From Database Gallery</a></center>
                </div>
            </div>
            <button type="submit" style="margin-top:10px;">Save Part</button>
        </form>
    </div>
"""

HTML_TAIL = """
    <div id="bulkActionBar" class="bulk-bar">
        <div class="bulk-content">
            <b id="bulkCountLabel" style="font-size:15px; color:#fd7e14;">0 items selected</b>
            <div class="bulk-actions">
                <button type="button" onclick="clearSelection()" style="background:#6c757d; font-weight:bold;">❌ Clear Selection</button>
                <button type="button" onclick="triggerBulkEdit()" style="background:#6f42c1; font-weight:bold;">✏️ Bulk Edit Selected</button>
            </div>
        </div>
    </div>
    
    <div class="box" style="background: #e1f5fe; border: 1px solid #b3e5fc;">
        <h3>🖼️ Bulk Upload Images to Database Gallery</h3>
        <p style="font-size:13px; margin: 0 0 10px 0; color:#0288d1;">Select or drag multiple images simultaneously. They will save into your container collection immediately.</p>
        <form action="/bulk_upload_images" method="POST" enctype="multipart/form-data" class="row2" onsubmit="handleFormSubmit(this);">
            <input type="file" name="gallery_images" accept="image/*" multiple required style="background:white; padding:4px;">
            <button type="submit" style="background:#0288d1;">Upload Staged Images</button>
        </form>
    </div>

    <div class="box" style="background: #eef1f6;">
        <h3>📥 Bulk Upload Parts via CSV File</h3>
        <p style="font-size:13px; margin: 0 0 10px 0; color:#555;">CSV columns must be in this order: <b>Location, Part Name, Item Type, Quantity, Notes, Purchase URL</b></p>
        <form action="/import" method="POST" enctype="multipart/form-data" class="row2" onsubmit="handleFormSubmit(this);">
            <input type="file" name="csv_file" accept=".csv" required style="background:white; padding:4px;">
            <button type="submit" style="background:#007bff;">Upload & Process</button>
        </form>
    </div>
    <div class="box">
        <h3>Manage Custom Item Types</h3>
        <form action="/add_cat" method="POST" class="row2" onsubmit="handleFormSubmit(this);"><input type="text" name="new_cat" placeholder="New category..." required><button type="submit" style="background:#6c757d;">Add Type</button></form>
    </div>
    <div class="box">
        <a href="/export" class="e-btn">📊 CSV Data File</a>
        <a href="/download_db" class="e-btn db-btn">💾 Download Raw Database file</a>
        <a href="/restore_db" class="e-btn r-btn" onclick="saveScrollPosition(); return confirm('Replace current data with last backup file?');">📤 Restore Backup</a>
        <a href="/backup_db" class="e-btn b-btn" onclick="saveScrollPosition();">📥 Save Backup</a>
        <h3>Search & Filter Inventory</h3>
        
        <form id="filterForm" action="/" method="GET" style="margin-bottom:15px;" onsubmit="event.preventDefault(); updateStickyControls();">
            <div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr auto; gap: 8px; align-items: center;">
                <input type="text" name="q" value="{{ query }}" placeholder="Search name, location, or notes..." style="margin:0;">
                
                <select name="filter_cat" onchange="updateStickyControls();" style="margin:0;">
                    <option value="">-- All Item Types --</option>
                    {% for cat in categories %}
                    <option value="{{ cat }}" {% if selected_cat == cat %}selected{% endif %}>Type: {{ cat }}</option>
                    {% endfor %}
                </select>
                
                <select name="filter_loc_type" onchange="updateStickyControls();" style="margin:0;">
                    <option value="">-- All Locations --</option>
                    <option value="drawer" {% if selected_loc_type == 'drawer' %}selected{% endif %}>Location: Drawers (D*)</option>
                    <option value="shelf" {% if selected_loc_type == 'shelf' %}selected{% endif %}>Location: Shelves</option>
                    <option value="unassigned" {% if selected_loc_type == 'unassigned' %}selected{% endif %}>Location: Unassigned</option>
                </select>
                
                <select name="sort" onchange="updateStickyControls();" style="margin:0;">
                    <option value="location" {% if sort_mode == 'location' %}selected{% endif %}>Sort by: Location Order</option>
                    <option value="newest" {% if sort_mode == 'newest' %}selected{% endif %}>Sort by: Last Added / Updated</option>
                    <option value="alpha" {% if sort_mode == 'alpha' %}selected{% endif %}>Sort by: Alphabetical (A-Z)</option>
                    <option value="quantity" {% if sort_mode == 'quantity' %}selected{% endif %}>Sort by: Low Stock First</option>
                </select>
                
                <button type="submit" class="s-btn" style="margin:0;">Filter</button>
            </div>
        </form>
        
        <table>
            <tr>
                <th style="width:4%; text-align:center;"><input type="checkbox" onclick="toggleSelectAll(this)" class="b-chk"></th>
                <th style="width:10%;">Photo</th>
                <th style="width:12%;">Location</th>
                <th style="width:24%;">Name & Details</th>
                <th style="width:14%;">Type</th>
                <th style="width:11%;">Qty</th>
                <th style="width:13%;">Updated (Phoenix)</th>
                <th style="width:12%;">Actions</th>
            </tr>
            {% for item_id, loc, name, cat, qty, notes, p_url, img, ts in items %}
            <tr>
                {% if edit_id == item_id %}
                <form action="/update/{{ item_id }}" method="POST" enctype="multipart/form-data" onsubmit="handleFormSubmit(this);">
                    <input type="hidden" name="existing_image_filename" id="edit_existing_image_{{ item_id }}" value="">
                    <td>-</td>
                    <td>
                        <input type="file" name="part_image" accept="image/*" style="font-size: 11px; width: 95px;"><br>
                        <div id="edit_preview_target_{{ item_id }}" style="margin: 4px 0;">
                            {% if img %}<img src="/images/{{ img }}" class="part-img"><small style="color:#666;">Current: {{ img }}</small>{% endif %}
                        </div>
                        <a class="media-link" onclick="openImageGallery('edit_existing_image_' + item_id, 'edit_preview_target_' + item_id)" style="font-size:10px;">📋 Use Existing</a>
                    </td>
                    <td><input type="text" name="location" value="{{ loc }}" class="t-input" required></td>
                    <td>
                        <input type="text" name="part_name" value="{{ name }}" class="t-input" required><br>
                        <input type="text" name="notes" value="{{ notes }}" class="t-input" placeholder="Notes"><br>
                        <input type="text" name="purchase_url" value="{{ p_url }}" class="t-input" placeholder="Purchase URL">
                    </td>
                    <td><select name="category" class="t-input">{% for c in categories %}<option value="{{ c }}" {% if c == cat %}selected{% endif %}>{{ c }}</option>{% endfor %}</select></td>
                    <td><input type="number" name="quantity" value="{{ qty }}" class="t-input"></td>
                    <td class="time-text">{{ ts }}</td>
                    <td><button type="submit" class="save-btn">Save</button> <a href="?sort={{ sort_mode }}&q={{ query }}&filter_cat={{ selected_cat }}&filter_loc_type={{ selected_loc_type }}" onclick="saveScrollPosition();" class="edit-lnk" style="color:#666; margin-left:5px;">Cancel</a></td>
                </form>
                {% else %}
                <td style="text-align:center;"><input type="checkbox" value="{{ item_id }}" class="item-chk b-chk" onclick="saveSelection(); updateBulkBar();"></td>
                <td>{% if img %}<img src="/images/{{ img }}" class="part-img">{% else %}<span style="color:#ccc; font-size:11px;">No Photo</span>{% endif %}</td>
                <td><b>{{ loc }}</b></td>
                <td>{{ name }}<br><small style="color:#777;">{{ notes }}</small>{% if p_url %}<br><a href="{{ p_url }}" target="_blank" style="color:#28a745; text-decoration:none; font-weight:bold; font-size:13px;">🛒 Buy Link</a>{% endif %}</td>
                <td>{{ cat }}</td>
                <td><a href="/adjust/{{ item_id }}/minus" onclick="event.preventDefault(); location.href=this.href+'?sort='+sessionStorage.getItem('sticky_sort')+'&q='+sessionStorage.getItem('sticky_q')+'&filter_cat='+sessionStorage.getItem('sticky_cat')+'&filter_loc_type='+sessionStorage.getItem('sticky_loc_type');" class="qty-btn">-</a> <b>{{ qty }}</b> <a href="/adjust/{{ item_id }}/plus" onclick="event.preventDefault(); location.href=this.href+'?sort='+sessionStorage.getItem('sticky_sort')+'&q='+sessionStorage.getItem('sticky_q')+'&filter_cat='+sessionStorage.getItem('sticky_cat')+'&filter_loc_type='+sessionStorage.getItem('sticky_loc_type');" class="qty-btn">+</a></td>
                <td class="time-text">{{ ts }}</td>
                <td><a href="?edit={{ item_id }}&sort={{ sort_mode }}&q={{ query }}&filter_cat={{ selected_cat }}&filter_loc_type={{ selected_loc_type }}" onclick="saveScrollPosition();" class="edit-lnk">Edit</a><form action="/delete/{{ item_id }}" method="POST" style="display:inline;" onsubmit="handleFormSubmit(this); return confirm('Delete?');"><button type="submit" class="del-btn">Delete</button></form></td>
                {% endif %}
            </tr>
            {% endfor %}
        </table>
    </div>
</body>
</html>"""

@app.route("/images/<filename>")
def get_image(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/api/existing_images")
def existing_images_api():
    try:
        files = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg'))]
        return jsonify(sorted(files))
    except:
        return jsonify([])

@app.route("/")
def index():
    q = (request.args.get("q") or request.form.get("q", "")).strip()
    edit_id = request.args.get("edit", type=int)
    sort_mode = (request.args.get("sort") or request.form.get("sort", "location")).strip()
    selected_cat = (request.args.get("filter_cat") or request.form.get("filter_cat", "")).strip()
    selected_loc_type = (request.args.get("filter_loc_type") or request.form.get("filter_loc_type", "")).strip()
    
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM categories ORDER BY name")
    
    # SYSTEM EXTRACTOR RESOLUTION: Pulls out string item types from database array tuples cleanly
    categories = [r[0] for r in cur.fetchall()]
    
    query_parts = ["1=1"]
    params = []
    
    if q:
        query_parts.append("(part_name LIKE ? OR location LIKE ? OR category LIKE ? OR notes LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"])
    
    if selected_cat:
        query_parts.append("category = ?")
        params.append(selected_cat)
        
    if selected_loc_type == "unassigned":
        query_parts.append("location = 'UNASSIGNED'")
    elif selected_loc_type == "drawer":
        query_parts.append("location LIKE 'D%' AND location NOT LIKE 'SHELF%'")
    elif selected_loc_type == "shelf":
        query_parts.append("location != 'UNASSIGNED' AND (location LIKE 'SHELF%' OR location NOT LIKE 'D%')")

    sort_sql = "ORDER BY location ASC"
    if sort_mode == "newest":
        sort_sql = "ORDER BY last_updated DESC"
    elif sort_mode == "alpha":
        sort_sql = "ORDER BY part_name ASC"
    elif sort_mode == "quantity":
        sort_sql = "ORDER BY quantity ASC, location ASC"

    where_clause = " AND ".join(query_parts)
    sql = f"SELECT id, location, part_name, category, quantity, notes, purchase_url, image_filename, last_updated FROM inventory WHERE {where_clause} {sort_sql} LIMIT 1000"
    
    cur.execute(sql, params)
    items = cur.fetchall()
    conn.close()
    return render_template_string(HTML_PAGE + HTML_TAIL, items=items, query=q, categories=categories, edit_id=edit_id, sort_mode=sort_mode, selected_cat=selected_cat, selected_loc_type=selected_loc_type)

@app.route("/download_db")
def download_db():
    if os.path.exists(DB_FILE): return send_file(DB_FILE, as_attachment=True, download_name="workshop_inventory.db")
    return redirect("/")

@app.route("/backup_db")
def backup_db():
    if os.path.exists(DB_FILE): shutil.copy(DB_FILE, os.path.join(BACKUP_FOLDER, "inventory_backup.db"))
    return redirect("/")

@app.route("/restore_db")
def restore_db():
    src = os.path.join(BACKUP_FOLDER, "inventory_backup.db")
    if os.path.exists(src): shutil.copy(src, DB_FILE)
    return redirect("/")

@app.route("/add", methods=["POST"])
def add():
    mode = request.form.get("loc_type")
    if mode == "unassigned": loc = "UNASSIGNED"
    elif mode == "shelf": loc = (request.form.get("shelf_name") or "").strip().upper() or "SHELF"
    else: loc = f"{request.form.get('drawer')}-{request.form.get('row_letter')}{request.form.get('col_num')}"
    
    name = (request.form.get('part_name') or "").strip()
    cat = request.form.get('category')
    qty = request.form.get('quantity', 0)
    notes = (request.form.get('notes') or "").strip()
    p_url = (request.form.get('purchase_url') or "").strip()
    ts = get_phoenix_time()
    
    img_file = request.files.get('part_image')
    img_name = (request.form.get('existing_image_filename') or "").strip()
    if img_file and img_file.filename != "":
        img_name = secure_filename(img_file.filename)
        img_file.save(os.path.join(app.config['UPLOAD_FOLDER'], img_name))

    conn = sqlite3.connect(DB_FILE)
    conn.execute("INSERT OR IGNORE INTO inventory (location, part_name, category, quantity, notes, purchase_url, image_filename, last_updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (loc, name, cat, qty, notes, p_url, img_name, ts))
    conn.commit()
    conn.close()
    
    q = request.form.get("q", "")
    sort_mode = request.form.get("sort", "location")
    selected_cat = request.form.get("filter_cat", "")
    selected_loc_type = request.form.get("filter_loc_type", "")
    return redirect(f"/?sort={sort_mode}&q={q}&filter_cat={selected_cat}&filter_loc_type={selected_loc_type}")

@app.route("/bulk_upload_images", methods=["POST"])
def bulk_upload_images():
    uploaded_files = request.files.getlist("gallery_images")
    for f in uploaded_files:
        if f and f.filename != "":
            img_name = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], img_name))
    
    q = request.form.get("q", "")
    sort_mode = request.form.get("sort", "location")
    selected_cat = request.form.get("filter_cat", "")
    selected_loc_type = request.form.get("filter_loc_type", "")
    return redirect(f"/?sort={sort_mode}&q={q}&filter_cat={selected_cat}&filter_loc_type={selected_loc_type}")

@app.route("/update/<int:item_id>", methods=["POST"])
def update_item(item_id):
    ts = get_phoenix_time()
    img_file = request.files.get('part_image')
    img_name = (request.form.get('existing_image_filename') or "").strip()
    
    q = request.form.get("q", "")
    sort_mode = request.form.get("sort", "location")
    selected_cat = request.form.get("filter_cat", "")
    selected_loc_type = request.form.get("filter_loc_type", "")
    
    loc_input = (request.form.get('location') or 'UNASSIGNED').strip().upper()
    part_input = (request.form.get('part_name') or 'Unnamed Part').strip()
    cat_input = request.form.get('category', '')
    qty_input = request.form.get('quantity', 0)
    notes_input = (request.form.get('notes') or '').strip()
    url_input = (request.form.get('purchase_url') or '').strip()

    conn = sqlite3.connect(DB_FILE)
    if img_file and img_file.filename != "":
        img_name = secure_filename(img_file.filename)
        img_file.save(os.path.join(app.config['UPLOAD_FOLDER'], img_name))
        conn.execute("UPDATE inventory SET location = ?, part_name = ?, category = ?, quantity = ?, notes = ?, purchase_url = ?, image_filename = ?, last_updated = ? WHERE id = ?", (loc_input, part_input, cat_input, qty_input, notes_input, url_input, img_name, ts, item_id))
    else:
        if img_name != "":
            conn.execute("UPDATE inventory SET location = ?, part_name = ?, category = ?, quantity = ?, notes = ?, purchase_url = ?, image_filename = ?, last_updated = ? WHERE id = ?", (loc_input, part_input, cat_input, qty_input, notes_input, url_input, img_name, ts, item_id))
        else:
            conn.execute("UPDATE inventory SET location = ?, part_name = ?, category = ?, quantity = ?, notes = ?, purchase_url = ?, last_updated = ? WHERE id = ?", (loc_input, part_input, cat_input, qty_input, notes_input, url_input, ts, item_id))
    conn.commit()
    conn.close()
    return redirect(f"/?sort={sort_mode}&q={q}&filter_cat={selected_cat}&filter_loc_type={selected_loc_type}")

@app.route("/bulk_update", methods=["POST"])
def bulk_update():
    raw_ids = request.form.get("bulk_ids", "").strip()
    if not raw_ids: return redirect("/")
    target_ids = [int(i) for i in raw_ids.split(",") if i.isdigit()]
    
    loc_mode = request.form.get("bulk_loc_type", "unchanged")
    loc = None
    if loc_mode == "unassigned": loc = "UNASSIGNED"
    elif loc_mode == "shelf": loc = (request.form.get("bulk_shelf_name") or "").strip().upper() or "SHELF"
    elif loc_mode == "drawer": loc = f"{request.form.get('bulk_drawer')}-{request.form.get('bulk_row_letter')}{request.form.get('bulk_col_num')}"
    
    cat = (request.form.get("bulk_category") or "").strip()
    img = (request.form.get("bulk_image_filename") or "").strip()
    ts = get_phoenix_time()
    
    if len(target_ids) > 0:
        query_parts = []
        params = []
        if loc is not None: query_parts.append("location = ?"); params.append(loc)
        if cat: query_parts.append("category = ?"); params.append(cat)
        if img: query_parts.append("image_filename = ?"); params.append(img)
        
        if query_parts:
            query_parts.append("last_updated = ?")
            params.append(ts)
            sql = f"UPDATE inventory SET {', '.join(query_parts)} WHERE id IN ({', '.join(['?']*len(target_ids))})"
            params.extend(target_ids)
            conn = sqlite3.connect(DB_FILE)
            conn.execute(sql, params)
            conn.commit()
            conn.close()
        
    q = request.form.get("q", "")
    sort_mode = request.form.get("sort", "location")
    selected_cat = request.form.get("filter_cat", "")
    selected_loc_type = request.form.get("filter_loc_type", "")
    return redirect(f"/?sort={sort_mode}&q={q}&filter_cat={selected_cat}&filter_loc_type={selected_loc_type}")

@app.route("/import", methods=["POST"])
def import_csv():
    file = request.files.get("csv_file")
    if not file or not file.filename.endswith('.csv'): return redirect("/")
    stream = io.StringIO(file.stream.read().decode("UTF-8"), newline=None)
    reader = csv.reader(stream)
    next(reader, None)
    ts = get_phoenix_time()
    conn = sqlite3.connect(DB_FILE)
    for row in reader:
        if len(row) >= 4:
            p_url = row[5].strip() if len(row) > 5 else ""
            conn.execute("INSERT OR IGNORE INTO inventory (location, part_name, category, quantity, notes, purchase_url, image_filename, last_updated) VALUES (?, ?, ?, ?, ?, ?, '', ?)", (row[0].strip().upper(), row[1].strip(), row[2].strip(), int(row[3] or 0), row[4].strip(), p_url, ts))
    conn.commit()
    conn.close()
    
    q = request.form.get("q", "")
    sort_mode = request.form.get("sort", "location")
    selected_cat = request.form.get("filter_cat", "")
    selected_loc_type = request.form.get("filter_loc_type", "")
    return redirect(f"/?sort={sort_mode}&q={q}&filter_cat={selected_cat}&filter_loc_type={selected_loc_type}")

@app.route("/adjust/<int:item_id>/<string:direction>")
def adjust(item_id, direction):
    q = request.args.get("q", "")
    sort_mode = request.args.get("sort", "location")
    selected_cat = request.args.get("filter_cat", "")
    selected_loc_type = request.args.get("filter_loc_type", "")
    amt = 1 if direction == "plus" else -1
    ts = get_phoenix_time()
    conn = sqlite3.connect(DB_FILE)
    conn.execute("UPDATE inventory SET quantity = MAX(0, quantity + ?), last_updated = ? WHERE id = ?", (amt, ts, item_id))
    conn.commit()
    conn.close()
    return redirect(f"/?sort={sort_mode}&q={q}&filter_cat={selected_cat}&filter_loc_type={selected_loc_type}")

@app.route("/delete/<int:item_id>", methods=["POST"])
def delete_item(item_id):
    q = request.args.get("q", "")
    sort_mode = request.args.get("sort", "location")
    selected_cat = request.args.get("filter_cat", "")
    selected_loc_type = request.args.get("filter_loc_type", "")
    conn = sqlite3.connect(DB_FILE)
    conn.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()
    return redirect(f"/?sort={sort_mode}&q={q}&filter_cat={selected_cat}&filter_loc_type={selected_loc_type}")

@app.route("/add_cat", methods=["POST"])
def add_cat():
    c = (request.form.get("new_cat") or "").strip()
    if c:
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.execute("INSERT INTO categories (name) VALUES (?)", (c,))
            conn.commit()
            conn.close()
        except: pass
    
    q = request.form.get("q", "")
    sort_mode = request.form.get("sort", "location")
    selected_cat = request.form.get("filter_cat", "")
    selected_loc_type = request.form.get("filter_loc_type", "")
    return redirect(f"/?sort={sort_mode}&q={q}&filter_cat={selected_cat}&filter_loc_type={selected_loc_type}")

@app.route("/export")
def export():
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["Location", "Part Name", "Item Type", "Quantity", "Notes", "Purchase URL", "Image Filename", "Last Updated"])
    conn = sqlite3.connect(DB_FILE)
    for r in conn.cursor().execute("SELECT location, part_name, category, quantity, notes, purchase_url, image_filename, last_updated FROM inventory ORDER BY location").fetchall():
        w.writerow(r)
    conn.close()
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment; filename=inventory.csv"})

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=False)
