
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js')
                    .then(reg => console.log('Service Worker registered successfully.'))
                    .catch(err => console.log('Service Worker registration failed:', err));
            });
        }
    





        // ---- Apply saved primary colour immediately (before CSS loads) ----
        (function() {
            const PURPLE = '#a855f7';
            const hotelId = '{{ session.hotel_id }}';

            // Migration: old key stored 'dark'/'light' — rescue it and clear the bad colour value
            const oldVal = localStorage.getItem('joy_theme_' + hotelId);
            if (oldVal === 'dark' || oldVal === 'light') {
                localStorage.setItem('joy_darkmode_' + hotelId, oldVal);
                localStorage.removeItem('joy_theme_' + hotelId);
            } else if (oldVal) {
                // old key had a real hex colour — migrate it to new key
                if (!localStorage.getItem('joy_color_' + hotelId)) {
                    localStorage.setItem('joy_color_' + hotelId, oldVal);
                }
                localStorage.removeItem('joy_theme_' + hotelId);
            }

            const savedColor = localStorage.getItem('joy_color_' + hotelId) || PURPLE;
            document.documentElement.style.setProperty('--primary-color', savedColor);
            const adj = (hex, amt) => '#' + hex.replace(/^#/, '').replace(/../g, c =>
                ('0' + Math.min(255, Math.max(0, parseInt(c, 16) + amt)).toString(16)).slice(-2));
            document.documentElement.style.setProperty('--primary-hover', adj(savedColor, -20));
            // Persist so it survives every refresh without user needing to click Save
            if (!localStorage.getItem('joy_color_' + hotelId)) {
                localStorage.setItem('joy_color_' + hotelId, PURPLE);
            }
        })();
    


        // --- Core Application State ---
        let currentRoom = null;
        let allRooms = [];
        let calendarInstance = null;
        let revenueChartInstance = null; // For financial charts
        let expenseChartInstance = null; // For financial charts
        let selectedReservedRoom = null; // For room management
        // --- Global State Vars ---
        window.forceOverrideBooking = false;
        window.pendingOverrideType = null;
        window.pendingRoomOverride = false;
        window.targetRoom = null;
        window.pendingForceOverride = false;
        window.checkoutRoomId = null;
        window.checkoutBookingId = null;

        /**
         * Custom Modal Popups
         */
        window.showAlert = function (title, message, type = 'info') {
            const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
            document.getElementById('alertIcon').textContent = icons[type] || icons.info;
            document.getElementById('alertTitle').textContent = title;
            document.getElementById('alertMessage').textContent = message;
            document.getElementById('customAlert').classList.add('show');
        };

        window.showConfirm = function (title, message, callback) {
            document.getElementById('confirmTitle').textContent = title;
            document.getElementById('confirmMessage').textContent = message;
            const yesBtn = document.getElementById('confirmYes');
            // Remove previous listeners
            const newBtn = yesBtn.cloneNode(true);
            yesBtn.parentNode.replaceChild(newBtn, yesBtn);
            newBtn.onclick = () => {
                closeModal('customConfirm');
                callback();
            };
            document.getElementById('customConfirm').classList.add('show');
        };

        const helpDocs = {
            'rooms': {
                title: 'Room Management Guide',
                content: `
                    <h4>🗝️ How to Check-In</h4>
                    <ul>
                        <li><b>Green Cards</b>: Available rooms. Tap one to start a booking.</li>
                        <li><b>Red Cards</b>: Occupied. Tap to view bill or add charges.</li>
                        <li><b>ID Photos</b>: Always take clear photos of Guest ID (Front/Back).</li>
                        <li><b>Groups</b>: Use "Additional Rooms" to book multiple rooms for one guest.</li>
                    </ul>
                `
            },
            'finance': {
                title: 'Financial Ledger Guide',
                content: `
                    <h4>📊 Understanding Finances</h4>
                    <ul>
                        <li><b>Revenue</b>: Total money collected from bookings and services.</li>
                        <li><b>Expenses</b>: Total spent on utilities, salaries, etc.</li>
                        <li><b>Filters</b>: Use the top bar to filter by Date, Month, or Year.</li>
                    </ul>
                `
            },
            'reports': {
                title: 'Performance Reports Guide',
                content: `
                    <h4>📑 Detailed Analytics</h4>
                    <ul>
                        <li><b>Aggregations</b>: View monthly and yearly growth charts.</li>
                        <li><b>Export</b>: Click 'Export Excel' or 'Export PDF' to download reports for accounting.</li>
                    </ul>
                `
            },
            'guests': {
                title: 'Guest History Guide',
                content: `
                    <h4>👥 Managing Guests</h4>
                    <ul>
                        <li><b>Search</b>: Find any guest using their phone number.</li>
                        <li><b>Edit Profile</b>: Update contact details or ID info by tapping the pencil icon.</li>
                        <li><b>Status</b>: Track 'Regular' vs 'New' guests automatically.</li>
                    </ul>
                `
            },
            'expenses': {
                title: 'Expense Tracker Guide',
                content: `
                    <h4>💸 Managing Spend</h4>
                    <ul>
                        <li><b>Add Expense</b>: Log every spend (Salaries, Water, Electricity).</li>
                        <li><b>Categories</b>: Group expenses to see where money is going.</li>
                        <li><b>Delete</b>: Remove accidental entries using the red delete button.</li>
                    </ul>
                `
            },
            'calendar': {
                title: 'Reservation Calendar Guide',
                content: `
                    <h4>📅 Planning Ahead</h4>
                    <ul>
                        <li><b>Future Bookings</b>: Check upcoming arrivals at a glance.</li>
                        <li><b>Drag & Drop</b>: Easily change guest stay dates by dragging their name.</li>
                    </ul>
                `
            },
            'support': {
                title: 'Support Team Contact',
                content: `
                    <h4>📥 Get Assistance</h4>
                    <p>If you face any issues, contact the support team:</p>
                    <ul>
                        <li>📞 <b>Phone</b>: 8956364864</li>
                        <li>📧 <b>Email</b>: joyhotels500@gmail.com</li>
                    </ul>
                    <p>Technician help is available 24/7 via the Settings > Support panel.</p>
                `
            },
            'system': {
                title: 'System Maintenance',
                content: `
                    <h4>🛡️ Data Security</h4>
                    <ul>
                        <li><b>Backups</b>: Download your database monthly to keep data safe.</li>
                        <li><b>Announcements</b>: Check the top banner for system updates.</li>
                    </ul>
                `
            }
        };

        window.openStaffHelp = function (section) {
            const doc = helpDocs[section];
            const titleEl = document.getElementById('helpTitle');
            const contentEl = document.getElementById('helpContent');

            if (doc) {
                titleEl.textContent = '📖 ' + doc.title;
                contentEl.innerHTML = doc.content;
            } else {
                titleEl.textContent = '📖 JoyHotels Staff Guide';
                contentEl.innerHTML = document.getElementById('fullGuide').outerHTML;
            }
            document.getElementById('staffHelpModal').classList.add('show');
        };


        // --- Initialization ---
        // Check for Announcements
        async function checkAnnouncements() {
            try {
                const res = await fetch('/api/public/announcement');
                const data = await res.json();
                if (data.has_announcement) {
                    document.getElementById('announceMsg').innerText = data.message;
                    const icons = { 'info': '📢', 'warning': '⚠️', 'success': '🎉' };
                    document.getElementById('announceIcon').innerText = icons[data.type] || '📢';
                    document.getElementById('announcementModal').style.display = 'flex';
                }
            } catch (e) { console.log('No announcements'); }
        }

        document.addEventListener('DOMContentLoaded', () => {
            // Restore dark/light mode (separate key from colour)
            const savedMode = localStorage.getItem('joy_darkmode_{{ session.hotel_id }}');
            if (savedMode) applyTheme(savedMode);
            // else default (dark) already set by CSS data-theme attribute

            // Check Announce
            checkAnnouncements();
            // Set initial page
            showPage('dashboard');
        });

        // --- Navigation ---
        function showPage(pageId) {
            // Hide all pages, show selected
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            const targetPage = document.getElementById(pageId);
            if (targetPage) targetPage.classList.add('active');

            // Update nav buttons
            document.querySelectorAll('.nav-btn').forEach(btn => {
                btn.classList.remove('active');
                // Highlight button based on the pageId it triggers
                const onClickStr = btn.getAttribute('onclick') || '';
                if (onClickStr.includes(`showPage('${pageId}')`)) {
                    btn.classList.add('active');
                }
            });

            // Specific page loading logic
            if (pageId === 'dashboard') loadRooms();
            else if (pageId === 'financial') updateFinancials();
            else if (pageId === 'guests') loadGuests();
            else if (pageId === 'calendar-page') loadCalendar();
            else if (pageId === 'expenses') {
                loadExpenses();
                const expDateInput = document.getElementById('expenseDate');
                if (expDateInput && !expDateInput.value) {
                    expDateInput.value = new Date().toISOString().split('T')[0];
                }
            }
            else if (pageId === 'reports-page') loadReports();
            else if (pageId === 'system') { /* No specific load function needed for system page */ }
        }

        // --- Theme Management ---
        function applyTheme(theme) {
            document.body.setAttribute('data-theme', theme);
            const btn = document.querySelector('.theme-toggle');
            if (btn) btn.textContent = theme === 'dark' ? '🌓' : '☀️';
        }

        function toggleTheme() {
            const currentTheme = document.body.getAttribute('data-theme') || 'dark';
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            applyTheme(newTheme);
            localStorage.setItem('joy_darkmode_{{ session.hotel_id }}', newTheme);
        }

        // --- Export & Printing ---
        function exportToExcel(elementId, fileName) {
            const table = document.getElementById(elementId);
            // Used simple SheetJS extraction
            const wb = XLSX.utils.table_to_book(table || document.querySelector(`#${elementId} table`), { sheet: "Sheet 1" });
            XLSX.writeFile(wb, `${fileName}_${new Date().toISOString().slice(0, 10)}.xlsx`);
        }

        function exportToPDF(elementId, fileName) {
            const element = document.getElementById(elementId);
            const opt = {
                margin: 10,
                filename: `${fileName}_${new Date().toISOString().slice(0, 10)}.pdf`,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2 },
                jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
            };
            html2pdf().set(opt).from(element).save();
        }

        function setBackupSummaryDate() {
            const dateElement = document.getElementById('backupDateExport');
            if (dateElement) {
                dateElement.textContent = new Date().toLocaleDateString();
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            setBackupSummaryDate();
        });

        // --- Room Management ---
        async function loadRooms() {
            try {
                const response = await fetch('/api/rooms');
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                allRooms = await response.json();

                const grid = document.getElementById('roomsGrid');
                if (!grid) return; // Exit if roomsGrid is not on the current page
                grid.innerHTML = '';

                let stats = { available: 0, occupied: 0, dirty: 0, reserved: 0, total: allRooms.length };

                if (!allRooms || allRooms.length === 0) {
                    grid.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 2rem; color: var(--text-secondary);">No rooms found. Add a room to get started!</div>';
                }

                allRooms.forEach(room => {
                    const status = room.status || 'available';
                    if (stats.hasOwnProperty(status)) {
                        stats[status]++;
                    } else {
                        stats.available++; // Default to available if status is unknown
                    }

                    const card = document.createElement('div');
                    card.className = `room-card ${status}`;
                    card.onclick = () => handleRoomClick(room);

                    card.innerHTML = `
                        <div class="room-number">${room.room_id}</div>
                        <div class="room-type">${room.room_type || 'Standard'}</div>
                        <div class="room-status" style="${status === 'reserved' ? 'color:#3b82f6' : ''}">
                            ${status.charAt(0).toUpperCase() + status.slice(1)}
                        </div>
                        ${(status === 'occupied' || status === 'reserved') ?
                            `<div style="font-size: 0.8rem; margin-top: 5px; color: var(--text-primary);">👤 ${room.guest_name || 'Guest'}</div>` : ''}
                    `;
                    grid.appendChild(card);
                });

                // Update Top Stats
                if (document.getElementById('availableCount')) document.getElementById('availableCount').textContent = stats.available;
                if (document.getElementById('occupiedCount')) document.getElementById('occupiedCount').textContent = stats.occupied;
                if (document.getElementById('dirtyCount')) document.getElementById('dirtyCount').textContent = stats.dirty;

                const occupancyRate = stats.total > 0 ? Math.round((stats.occupied / stats.total) * 100) : 0;
                if (document.getElementById('occupancyRate')) document.getElementById('occupancyRate').textContent = `${occupancyRate}%`;

            } catch (error) {
                console.error('Error loading rooms:', error);
                showAlert('Warning', 'Failed to load rooms. Please check your connection.', 'warning');
            }
        }

        function handleRoomClick(room) {
            if (room.status === 'available') openBookingModal(room);
            else if (room.status === 'reserved') {
                selectedReservedRoom = room;
                document.getElementById('resGuestName').textContent = room.guest_name;
                document.getElementById('manageReservationModal').classList.add('show');
            }
            else if (room.status === 'occupied') {
                if (room.booking_id) openCheckoutModal(room);
                else showAlert('Error', 'Room marked occupied but no booking ID found.', 'error');
            }
            else if (room.status === 'dirty') {
                showConfirm('Room Cleaning', `Mark Room ${room.room_id} as Clean?`, () => cleanRoom(room.room_id));
            }
        }

        async function cleanRoom(roomId) {
            try {
                const response = await fetch(`/api/clean-room/${roomId}`, { method: 'POST' });
                const result = await response.json();
                if (result.success) loadRooms();
            } catch (error) { console.error('Error cleaning room:', error); }
        }

        async function addNewRoom() {
            const roomId = document.getElementById('newRoomId').value;
            const roomType = document.getElementById('newRoomType').value;

            if (!roomId) return alert('Enter Room Number');

            try {
                const response = await fetch('/api/rooms/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ room_id: roomId, room_type: roomType, force_override: window.pendingRoomOverride || false })
                });

                const result = await response.json();

                if (result.requires_confirmation) {
                    document.getElementById('conflictMessage').textContent = result.message;
                    document.getElementById('conflictModal').classList.add('show');
                    window.pendingRoomOverride = true; // Use a specific flag for room override
                    return;
                }

                if (result.success) {
                    closeModal('addRoomModal');
                    loadRooms();
                    document.getElementById('newRoomId').value = '';
                    window.pendingRoomOverride = false;
                } else {
                    showAlert('Error', result.message, 'error');
                }
            } catch (e) {
                console.error(e);
                showAlert('Error', 'Error adding room', 'error');
            }
        }

        function proceedCheckInFromRes() {
            closeModal('manageReservationModal');
            if (selectedReservedRoom) {
                window.forceOverrideBooking = true;
                openBookingModal(selectedReservedRoom);
                // Force pre-fill name after modal opens (small delay to ensure DOM update)
                setTimeout(() => {
                    const nameInput = document.getElementById('guestName');
                    if (nameInput) {
                        nameInput.value = selectedReservedRoom.guest_name;
                        // Also try to fetch guest details if phone matches
                        // selectedReservedRoom might not have phone, usually reservations are made by name first
                    }
                }, 100);
            }
        }

        async function cancelReservation() {
            showConfirm('Cancel Reservation', 'Are you sure you want to CANCEL this reservation? This cannot be undone.', async () => {
                try {
                    const response = await fetch('/api/reserve', {
                        method: 'DELETE',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            room_id: selectedReservedRoom.room_id,
                            guest_name: selectedReservedRoom.guest_name
                        })
                    });
                    const result = await response.json();
                    if (result.success) {
                        closeModal('manageReservationModal');
                        loadRooms();
                    } else {
                        showAlert('Error', result.message, 'error');
                    }
                } catch (e) { console.error(e); }
            });
        }

        // --- Booking Flow ---
        function formatAmPmDateTime(localISO) {
            if (!localISO) return '';
            const parts = localISO.split('T');
            const dateParts = parts[0].split('-');
            const timeParts = (parts[1] || '00:00').split(':');
            let hour = parseInt(timeParts[0], 10);
            const minute = timeParts[1] || '00';
            const period = hour >= 12 ? 'PM' : 'AM';
            hour = hour % 12 || 12;
            return `${dateParts[2]}-${dateParts[1]}-${dateParts[0]} ${String(hour).padStart(2, '0')}:${minute} ${period}`;
        }

        function parseAmPmDateTime(value) {
            const match = value.trim().match(/^(\d{1,2})-(\d{1,2})-(\d{4})\s+(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
            if (!match) return value;
            let hour = parseInt(match[4], 10);
            const period = match[6].toUpperCase();
            if (hour < 1 || hour > 12 || parseInt(match[5], 10) > 59) return value;
            if (period === 'PM' && hour !== 12) hour += 12;
            if (period === 'AM' && hour === 12) hour = 0;
            return `${match[3]}-${match[2].padStart(2, '0')}-${match[1].padStart(2, '0')}T${String(hour).padStart(2, '0')}:${match[5]}`;
        }

        function openBookingModal(room) {
            window.targetRoom = room; // Store target room globally for form submission
            // Only reset if NOT coming from the reservation flow
            if (!window.forceOverrideBooking) window.forceOverrideBooking = false;

            document.getElementById('bookingRoomId').value = room.room_id;
            document.getElementById('modalRoomNumber').textContent = room.room_id;
            document.getElementById('bookingForm').reset();
            document.getElementById('guestStatusBadge').textContent = '';
            document.getElementById('guestStatusBadge').style.backgroundColor = 'transparent';

            // Pre-fill check-in datetime-local with current time
            const now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            const checkinInput = document.getElementById('checkinTime');
            if (checkinInput) checkinInput.value = formatAmPmDateTime(now.toISOString().slice(0, 16));

            // Clear and add one additional member field by default (so 2 guest name fields are already visible)
            const membersContainer = document.getElementById('dashboardMembersContainer');
            if (membersContainer) {
                membersContainer.innerHTML = '';
                addDashboardMemberField();
            }

            // Populate Additional Rooms
            const container = document.getElementById('additionalRoomsSection');
            if (container) {
                container.innerHTML = '';
                allRooms.forEach(r => {
                    // Only show available rooms that are not the current room
                    if (r.status === 'available' && r.room_id !== room.room_id) {
                        const div = document.createElement('div');
                        div.style.cssText = 'display: inline-flex; align-items: center; gap: 4px; background: rgba(255,255,255,0.05); padding: 4px 8px; border-radius: 6px; font-size: 0.85rem;';
                        div.innerHTML = `
                            <input type="checkbox" name="additional_rooms" value="${r.room_id}" id="room_${r.room_id}">
                            <label for="room_${r.room_id}" style="margin: 0; cursor: pointer;">${r.room_id}</label>
                        `;
                        container.appendChild(div);
                    }
                });
            }

            document.getElementById('bookingModal').classList.add('show');
        }



        async function scanIDWithAI() {
            const fileInput = document.getElementById('idPhoto');
            if (!fileInput.files || fileInput.files.length === 0) {
                showAlert('Photo Required', 'Please select or take an ID photo first! / पहले पहचान पत्र का फोटो चुनें या खींचें।', 'warning');
                return;
            }

            const btn = document.getElementById('aiScanBtn');
            const origText = btn.innerHTML;
            btn.innerHTML = '⚡ Scanning...';
            btn.disabled = true;

            try {
                // Dynamic Tesseract loader if not loaded
                if (typeof Tesseract === 'undefined') {
                    await new Promise((resolve, reject) => {
                        const script = document.createElement('script');
                        script.src = 'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js';
                        script.onload = resolve;
                        script.onerror = reject;
                        document.head.appendChild(script);
                    });
                }

                const file = fileInput.files[0];
                const result = await Tesseract.recognize(file, 'eng', {
                    logger: m => {
                        if (m.status === 'recognizing text') {
                            btn.innerHTML = `⚡ ${Math.round(m.progress * 100)}%`;
                        }
                    }
                });

                const text = result.data.text || '';
                console.log('AI Extracted Text:', text);

                // Regular expressions for Indian ID cards (Aadhaar, Driving License, Voter ID, PAN)
                const aadhaarMatch = text.match(/\b[2-9]\d{3}\s?\d{4}\s?\d{4}\b/);
                const dlMatch = text.match(/\b[A-Z]{2}\s?\d{2}\s?\d{11}\b/i) || text.match(/\b[A-Z]{2}-\d{13}\b/i);
                const panMatch = text.match(/\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b/i);
                const voterMatch = text.match(/\b[A-Z]{3}\d{7}\b/i);

                let detectedID = '';
                if (aadhaarMatch) detectedID = aadhaarMatch[0].replace(/\s/g, '');
                else if (dlMatch) detectedID = dlMatch[0];
                else if (panMatch) detectedID = panMatch[0];
                else if (voterMatch) detectedID = voterMatch[0];

                if (detectedID) {
                    document.getElementById('guestId').value = detectedID;
                }

                // Extract lines for Name detection
                const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 2);
                let foundName = '';
                let foundAddress = '';

                // Common keywords to ignore
                const ignoreKeywords = ['GOVERNMENT', 'INDIA', 'INCOME', 'TAX', 'DEPARTMENT', 'ELECTION', 'COMMISSION', 'CARD', 'MALE', 'FEMALE', 'DOB', 'DATE', 'BIRTH', 'ADDRESS', 'DRIVING', 'LICENCE', 'SIGNATURE', 'NUMBER'];

                for (let line of lines) {
                    const upper = line.toUpperCase();
                    if (!ignoreKeywords.some(kw => upper.includes(kw)) && /^[A-Za-z\s.]{3,30}$/.test(line)) {
                        if (!foundName) {
                            foundName = line;
                        }
                    }
                    if (upper.includes('ADDRESS') || upper.includes('HNO') || upper.includes('STREET') || upper.includes('VILL') || upper.includes('POST') || upper.includes('DIST')) {
                        foundAddress += ' ' + line;
                    }
                }

                if (foundName) document.getElementById('guestName').value = foundName;
                if (foundAddress) document.getElementById('guestAddress').value = foundAddress.replace(/address\s*[:|-]?/i, '').trim();

                btn.innerHTML = '✅ Scanned!';
                btn.style.background = 'linear-gradient(135deg, #10b981, #059669)';
                setTimeout(() => {
                    btn.innerHTML = origText;
                    btn.style.background = '';
                    btn.disabled = false;
                }, 2000);

                showAlert('AI Scan Complete! ✨', `Scanned ID successfully!\nName: ${foundName || 'Manual check required'}\nID No: ${detectedID || 'Manual check required'}`, 'success');

            } catch (err) {
                console.error('AI Scan Error:', err);
                btn.innerHTML = origText;
                btn.disabled = false;
                showAlert('Scan Notice', 'Text scanned. Please verify extracted details.', 'info');
            }
        }

        function addDashboardMemberField(name = '', age = '') {
            const container = document.getElementById('dashboardMembersContainer');
            if (!container) return;
            const index = container.children.length + 1;
            const inputHTML = `
                <div class="member-input-row" style="display: flex; gap: 8px; margin-bottom: 8px; align-items: center;">
                    <input type="text" class="form-control dashboard-member-name" placeholder="Member ${index} Name" value="${name}" style="flex: 2;">
                    <input type="number" class="form-control dashboard-member-age" placeholder="Age" min="0" value="${age}" style="width: 80px; flex: 0 0 80px;">
                    <button type="button" onclick="this.parentElement.remove()" style="background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.4); border-radius: 8px; color: #ef4444; cursor: pointer; padding: 6px 10px; font-size: 1rem; line-height: 1;" title="Remove Member">❌</button>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', inputHTML);
        }

        document.getElementById('bookingForm').onsubmit = async (e) => {
            e.preventDefault();
            await submitBooking(e);
        };

        let selectedIdFiles = [];

        function handleIdPhotoSelection(input) {
            if (!input.files) return;
            for (let i = 0; i < input.files.length; i++) {
                selectedIdFiles.push(input.files[i]);
            }
            renderPhotoPreviews();
            input.value = '';
        }

        function removeSelectedPhoto(index) {
            selectedIdFiles.splice(index, 1);
            renderPhotoPreviews();
        }

        function renderPhotoPreviews() {
            const grid = document.getElementById('photoPreviewGrid');
            const textSpan = document.getElementById('fileButtonText');
            if (!grid) return;
            grid.innerHTML = '';
            
            if (selectedIdFiles.length === 0) {
                grid.style.display = 'none';
                if (textSpan) textSpan.textContent = 'Choose ID';
                return;
            }
            
            grid.style.display = 'flex';
            grid.style.flexWrap = 'wrap';
            grid.style.gap = '8px';
            grid.style.marginTop = '10px';
            
            if (textSpan) textSpan.textContent = `${selectedIdFiles.length} Selected`;
            
            selectedIdFiles.forEach((file, idx) => {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const wrapper = document.createElement('div');
                    wrapper.style.position = 'relative';
                    wrapper.style.width = '60px';
                    wrapper.style.height = '60px';
                    wrapper.style.borderRadius = '8px';
                    wrapper.style.overflow = 'hidden';
                    wrapper.style.border = '1px solid rgba(212, 175, 55, 0.6)';
                    
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.style.width = '100%';
                    img.style.height = '100%';
                    img.style.objectFit = 'cover';
                    
                    const delBtn = document.createElement('button');
                    delBtn.type = 'button';
                    delBtn.innerHTML = '&times;';
                    delBtn.style.position = 'absolute';
                    delBtn.style.top = '2px';
                    delBtn.style.right = '2px';
                    delBtn.style.background = 'rgba(239, 68, 68, 0.9)';
                    delBtn.style.color = '#fff';
                    delBtn.style.border = 'none';
                    delBtn.style.borderRadius = '50%';
                    delBtn.style.width = '18px';
                    delBtn.style.height = '18px';
                    delBtn.style.fontSize = '12px';
                    delBtn.style.fontWeight = 'bold';
                    delBtn.style.cursor = 'pointer';
                    delBtn.style.display = 'flex';
                    delBtn.style.alignItems = 'center';
                    delBtn.style.justifyContent = 'center';
                    delBtn.onclick = function(ev) {
                        ev.stopPropagation();
                        removeSelectedPhoto(idx);
                    };
                    
                    wrapper.appendChild(img);
                    wrapper.appendChild(delBtn);
                    grid.appendChild(wrapper);
                };
                reader.readAsDataURL(file);
            });
        }

        async function submitBooking(e) {
            const form = document.getElementById('bookingForm');

            // Process Main Guest Name & Age
            const guestNameInput = document.getElementById('guestName').value.trim();
            const guestAgeInput = document.getElementById('guestAge').value.trim();
            const finalGuestName = guestAgeInput ? `${guestNameInput} (${guestAgeInput})` : guestNameInput;

            // Gather additional members
            const memberRows = document.querySelectorAll('.member-input-row');
            const membersList = [];
            memberRows.forEach(row => {
                const nameInp = row.querySelector('.dashboard-member-name').value.trim();
                const ageInp = row.querySelector('.dashboard-member-age').value.trim();
                if (nameInp) {
                    membersList.push(ageInp ? `${nameInp} (${ageInp})` : nameInp);
                }
            });
            document.getElementById('dashboardMembersInput').value = JSON.stringify(membersList);

            if (selectedIdFiles.length < 1) {
                showAlert('Validation Error', 'Primary ID photo is compulsory.', 'warning');
                return;
            }
            if (membersList.length > 0 && selectedIdFiles.length < 2) {
                showAlert('Validation Error', 'Minimum 2 ID photos required when there are multiple guests.', 'warning');
                return;
            }

            const formData = new FormData(form);
            // Replace the raw guest_name with our combined one
            formData.set('guest_name', finalGuestName);
            formData.set('checkin_time', parseAmPmDateTime(formData.get('checkin_time')));
            formData.delete('id_photos');
            selectedIdFiles.forEach(file => {
                formData.append('id_photos', file);
            });

            // Handle multiple rooms
            const selectedRooms = [document.getElementById('bookingRoomId').value];
            document.querySelectorAll('input[name="additional_rooms"]:checked').forEach(cb => {
                selectedRooms.push(cb.value);
            });
            formData.append('room_ids', selectedRooms.join(','));

            if (window.forceOverrideBooking) {
                formData.append('force_override', 'true');
            }

            try {
                const response = await fetch('/api/book', { method: 'POST', body: formData });
                const result = await response.json();

                if (result.requires_confirmation) {
                    document.getElementById('conflictMessage').textContent = result.message;
                    document.getElementById('conflictModal').classList.add('show');
                    window.pendingOverrideType = 'booking';
                    return;
                }

                if (result.success) {
                    closeModal('bookingModal');
                    loadRooms();
                    loadFinancials();
                    form.reset();
                    selectedIdFiles = [];
                    renderPhotoPreviews();
                    window.forceOverrideBooking = false;
                    showAlert('Success', 'Booking Successful! 📅', 'success');
                } else {
                    showAlert('Booking Failed', result.message || 'Unknown error', 'error');
                }
            } catch (error) { console.error('Error booking room:', error); }
        }

        function confirmOverride() {
            closeModal('conflictModal');

            if (window.pendingRoomOverride) {
                window.pendingRoomOverride = false; // Reset flag
                addNewRoom(); // Retry adding room with override
            }
            else if (window.pendingOverrideType === 'booking') {
                window.forceOverrideBooking = true; // Set flag for booking
                submitBooking(); // Retry booking with override
                window.pendingOverrideType = null;
            }
        }

        // --- Checkout Flow ---
        async function openCheckoutModal(room) {
            if (!room.booking_id) return;
            try {
                const response = await fetch(`/api/booking/${room.booking_id}`);
                const booking = await response.json();
                document.getElementById('checkoutBookingId').value = booking.id;
                document.getElementById('checkoutRoomNumber').textContent = room.room_id; // Display current room, but checkout will clear all
                document.getElementById('checkoutGuestInfo').innerHTML = `
                    <p><strong>Guest:</strong> ${booking.guest_name}</p>
                    <p><strong>Check-in:</strong> ${booking.checkin_time}</p>
                    <p><strong>Initial:</strong> ₹${booking.amount}</p>
                `;
                document.getElementById('checkoutForm').reset();
                const now = new Date();
                now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
                document.getElementById('checkoutTime').value = formatAmPmDateTime(now.toISOString().slice(0, 16));
                document.getElementById('checkoutModal').classList.add('show');
            } catch (error) { console.error('Error details:', error); }
        }

        document.getElementById('checkoutForm').onsubmit = async (e) => {
            e.preventDefault();
            const data = {
                booking_id: document.getElementById('checkoutBookingId').value,
                checkout_time: parseAmPmDateTime(document.getElementById('checkoutTime').value),
                food: parseFloat(document.getElementById('foodCharges').value) || 0,
                laundry: parseFloat(document.getElementById('laundryCharges').value) || 0,
                water_bottle: parseFloat(document.getElementById('waterBottleCharges').value) || 0,
                car_wash: parseFloat(document.getElementById('carWashCharges').value) || 0
            };
            try {
                const response = await fetch('/api/checkout', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                const result = await response.json();
                if (result.success) {
                    closeModal('checkoutModal');
                    loadRooms();
                    loadFinancials();
                    showAlert('Success', 'Checkout Complete!', 'success');
                } else {
                    showAlert('Error', result.message, 'error');
                }
            } catch (error) { console.error('Error checking out:', error); }
        };

        // --- Financials & Analytics ---
        async function updateFinancials(date = null) {
            const range = document.getElementById('finTimeRange').value || '30days';
            let url = `/api/financials/ledger?range=${range}`;
            if (date) url = `/api/financials/ledger?date=${date}`;

            try {
                const response = await fetch(url);
                const data = await response.json();

                // 1. Update KPI Cards
                if (document.getElementById('totalRevenue')) document.getElementById('totalRevenue').textContent = `₹${data.revenue.toLocaleString()}`;
                if (document.getElementById('totalExpenses')) document.getElementById('totalExpenses').textContent = `₹${data.expenses.toLocaleString()}`;
                if (document.getElementById('netProfit')) document.getElementById('netProfit').textContent = `₹${data.profit.toLocaleString()}`;

                // 2. Render Charts
                renderCharts(data);

                // 3. Populate Ledger Table
                loadFinancialEntries(data.transactions);

            } catch (error) {
                console.error('Error loading financials:', error);
                showAlert('Error', 'Failed to load financial data.', 'error');
            }
        }

        function renderCharts(data) {
            const ctxRev = document.getElementById('revenueChart');
            const ctxExp = document.getElementById('expenseChart');

            if (ctxRev && data.chart_labels) {
                if (revenueChartInstance) revenueChartInstance.destroy();
                revenueChartInstance = new Chart(ctxRev.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: data.chart_labels,
                        datasets: [
                            {
                                label: 'Revenue',
                                data: data.chart_revenue,
                                borderColor: '#10b981',
                                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                                fill: true,
                                tension: 0.4
                            },
                            {
                                label: 'Expenses',
                                data: data.chart_expenses,
                                borderColor: '#ef4444',
                                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                                fill: true,
                                tension: 0.4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: true, position: 'top' } },
                        scales: {
                            y: { beginAtZero: true, grid: { color: 'rgba(128, 128, 128, 0.1)' } },
                            x: { grid: { display: false } }
                        }
                    }
                });
            }

            if (ctxExp && data.expense_breakdown) {
                if (expenseChartInstance) expenseChartInstance.destroy();
                expenseChartInstance = new Chart(ctxExp.getContext('2d'), {
                    type: 'doughnut',
                    data: {
                        labels: Object.keys(data.expense_breakdown),
                        datasets: [{
                            data: Object.values(data.expense_breakdown),
                            backgroundColor: ['#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6', '#ec4899', '#06b6d4']
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: 'bottom' } },
                        cutout: '70%'
                    }
                });
            }
        }

        function loadFinancialEntries(transactions) {
            const tbody = document.getElementById('ledgerTableBody');
            if (!tbody) return;

            tbody.innerHTML = transactions.map(t => `
                <tr>
                    <td>${t.date}</td>
                    <td>${t.description}</td>
                    <td><span class="badge ${t.type === 'income' ? 'bg-income' : 'bg-expense'}">${t.type.toUpperCase()}</span></td>
                    <td>${t.category}</td>
                    <td style="text-align: right; font-weight: 600; color: ${t.type === 'income' ? 'var(--success-color)' : 'var(--danger-color)'}">
                        ${t.type === 'income' ? '+' : '-'}₹${t.amount.toLocaleString()}
                    </td>
                    <td style="text-align: center;">
                        ${t.type === 'income' ? `<button class="btn btn-sm btn-primary" style="padding: 2px 8px; font-size: 0.75rem;" onclick="viewGuest(${t.id})">👤 View Profile</button>` : '-'}
                    </td>
                </tr>
            `).join('');
        }

        function searchLedgerByDate() {
            const date = document.getElementById('ledgerSpecificDate').value;
            if (!date) {
                showAlert('Error', 'Please select a date first', 'warning');
                return;
            }
            updateFinancials(date);
        }

        async function viewGuestProfile(bookingId) {
            try {
                const response = await fetch(`/api/guest/${bookingId}`);
                if (!response.ok) throw new Error('Guest not found');
                const guest = await response.json();

                // Reuse the guest detail modal or similar logic
                // For now, let's use the standard detail view pattern
                // If we have a dedicated guestModal, use that. 
                // Let's check how guests are viewed in the "Guest History" page.

                // For simplicity, let's show an alert with details or open the bill page
                // But the user asked for a "View Profile" which usually means details.

                // We'll show the info in a custom modal if possible.
                // Let's assume we can use showPage('guests') and highlight them? 
                // No, a modal is better.

                // Let's implement a quick detail modal for this.
                showAlert(`Guest Profile: ${guest.guest_name}`, `
                    <b>Phone:</b> ${guest.phone}<br>
                    <b>Room:</b> ${guest.room_id}<br>
                    <b>Address:</b> ${guest.address}<br>
                    <b>Check-in:</b> ${guest.checkin_time}<br>
                    <b>Status:</b> ${guest.status || 'Regular'}<br>
                    <hr>
                    <button class="btn btn-sm btn-primary" onclick="window.location.href='/bill/${bookingId}'">🧾 View Full Bill</button>
                `, 'info');

            } catch (error) {
                console.error('Error fetching guest profile:', error);
                showAlert('Error', 'Could not load guest profile', 'error');
            }
        }

        async function loadReports() {
            try {
                const response = await fetch('/api/reports');
                const data = await response.json();

                const mBody = document.getElementById('monthlyTableBody');
                if (mBody) {
                    mBody.innerHTML = (data.monthly || []).map(m => `
                        <tr>
                            <td><strong>${m.period}</strong></td>
                            <td style="color: var(--success-color); font-weight:600;">₹${m.revenue.toLocaleString()}</td>
                            <td style="color: var(--danger-color);">₹${m.expenses.toLocaleString()}</td>
                            <td style="font-weight:700; color: ${m.profit >= 0 ? 'var(--success-color)' : 'var(--danger-color)'}">₹${m.profit.toLocaleString()}</td>
                            <td><span class="badge bg-info" style="background:var(--info-color); color:white;">${m.rooms_booked} Rooms</span></td>
                        </tr>
                    `).join('');
                }

                const yBody = document.getElementById('yearlyTableBody');
                if (yBody) {
                    yBody.innerHTML = (data.yearly || []).map(y => `
                        <tr>
                            <td><strong>${y.period}</strong></td>
                            <td style="color: var(--success-color); font-weight:600;">₹${y.revenue.toLocaleString()}</td>
                            <td style="color: var(--danger-color);">₹${y.expenses.toLocaleString()}</td>
                            <td style="font-weight:700; color: ${y.profit >= 0 ? 'var(--success-color)' : 'var(--danger-color)'}">₹${y.profit.toLocaleString()}</td>
                            <td><span class="badge bg-info" style="background:var(--info-color); color:white;">${y.rooms_booked} Rooms</span></td>
                        </tr>
                    `).join('');
                }
            } catch (error) { console.error('Error loading reports:', error); }
        }

        function filterLedger(input) {
            const filter = input.value.toUpperCase();
            const rows = document.getElementById('ledgerTableBody').getElementsByTagName('tr');
            for (let row of rows) {
                row.style.display = row.innerText.toUpperCase().includes(filter) ? '' : 'none';
            }
        }

        // --- Guests ---
        async function loadGuests(params = {}) {
            try {
                let url = '/api/guests';
                const qs = new URLSearchParams(params).toString();
                if (qs) url += '?' + qs;

                const response = await fetch(url);
                const guests = await response.json();
                const tbody = document.getElementById('guestsTableBody');
                if (!tbody) return;

                if (!guests.length) {
                    tbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:2rem; color:var(--text-secondary);">No guests found for this period.</td></tr>`;
                    const rc = document.getElementById('guestResultCount');
                    if (rc) rc.textContent = '0 guests found';
                    return;
                }

                tbody.innerHTML = guests.map(guest => `
                    <tr>
                        <td>
                            ${guest.guest_name}
                            ${guest.members && guest.members.length ? `<br>${guest.members.join('<br>')}` : ''}
                        </td>
                        <td class="mobile-hide">${guest.phone}</td>
                        <td>${guest.room_id}</td>
                        <td class="mobile-hide">${guest.checkin_time}</td>
                        <td class="mobile-hide">${guest.checkout_time || '-'}</td>
                        <td><button class="btn btn-primary btn-sm" onclick="viewGuest(${guest.id})">View</button></td>
                    </tr>
                `).join('');

                const rc = document.getElementById('guestResultCount');
                if (rc) rc.textContent = `${guests.length} guest${guests.length !== 1 ? 's' : ''} found`;

            } catch (error) { console.error('Error loading guests:', error); }
        }

        // Toggle date/month pickers based on filter dropdown
        function onGuestFilterChange() {
            const filter = document.getElementById('guestDateFilter').value;
            const dp = document.getElementById('guestDatePicker');
            const mp = document.getElementById('guestMonthPicker');
            dp.style.display  = filter === 'date'  ? 'block' : 'none';
            mp.style.display  = filter === 'month' ? 'block' : 'none';
        }

        // Fetch from API with selected date/month
        async function runGuestSearch() {
            const filter = document.getElementById('guestDateFilter').value;
            const params = {};
            if (filter === 'date') {
                const val = document.getElementById('guestDatePicker').value;
                if (!val) return showAlert('Required', 'Please pick a date first.', 'warning');
                params.date = val;
            } else if (filter === 'month') {
                const val = document.getElementById('guestMonthPicker').value;
                if (!val) return showAlert('Required', 'Please pick a month first.', 'warning');
                params.month = val;
            }
            await loadGuests(params);
            // After API load, also apply any text typed
            filterGuestsLocal();
        }

        // Reset all filters back to All Time
        function clearGuestSearch() {
            document.getElementById('guestDateFilter').value = 'all';
            document.getElementById('guestDatePicker').style.display  = 'none';
            document.getElementById('guestMonthPicker').style.display = 'none';
            document.getElementById('guestSearchInput').value = '';
            const rc = document.getElementById('guestResultCount');
            if (rc) rc.textContent = '';
            loadGuests();
        }

        // Local text filter (runs on already-loaded rows without an API call)
        function filterGuestsLocal() {
            const input  = document.getElementById('guestSearchInput');
            if (!input) return;
            const filter = input.value.toUpperCase().trim();
            const tbody  = document.getElementById('guestsTableBody');
            if (!tbody) return;
            const rows   = tbody.getElementsByTagName('tr');
            let visible  = 0;

            for (let i = 0; i < rows.length; i++) {
                const tds = rows[i].getElementsByTagName('td');
                const name  = tds[0] ? (tds[0].textContent || '').toUpperCase() : '';
                const phone = tds[1] ? (tds[1].textContent || '').toUpperCase() : '';
                const room  = tds[2] ? (tds[2].textContent || '').toUpperCase() : '';
                const show  = !filter || name.includes(filter) || phone.includes(filter) || room.includes(filter);
                rows[i].style.display = show ? '' : 'none';
                if (show) visible++;
            }
            const rc = document.getElementById('guestResultCount');
            if (rc && rows.length) rc.textContent = `${visible} guest${visible !== 1 ? 's' : ''} found`;
        }

        // Keep old name working if referenced elsewhere
        function filterGuests() { filterGuestsLocal(); }


        async function viewGuest(guestId) {
            try {
                const response = await fetch(`/api/guest/${guestId}`);
                const guest = await response.json();

                // Fetch extra profile details (like email) from search_guest API
                const profileResp = await fetch(`/api/guests/search?phone=${guest.phone}`);
                const profile = await profileResp.json();
                const guestEmail = profile.success ? (profile.guest.email || '') : '';

                let photosHtml = guest.id_photo ? guest.id_photo.split(',').map(photo =>
                    `<a href="/static/${photo}" target="_blank"><img src="/static/${photo}" style="height: 80px; margin-right: 10px; border-radius: 4px;"></a>`
                ).join('') : 'No photos';

                const memberNames = Array.isArray(guest.members) ? guest.members : [];
                const allNames = [guest.guest_name, ...memberNames].join('<br>');

                document.getElementById('guestProfileContent').innerHTML = `
                    <div id="guestDisplayView">
                        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem;">
                            <div>
                                <p style="margin-bottom: 0.25rem; color: var(--text-secondary);">Guest Profile</p>
                                <h2 style="color: var(--text-primary); margin: 0; line-height: 1.2;">${allNames}</h2>
                                <p style="color: var(--gold); font-size: 0.9rem; margin-top: 0.5rem;">${guestEmail}</p>
                            </div>
                            <button class="btn btn-outline btn-sm" onclick="toggleGuestEdit(true); return false;">✏️ Edit Profile</button>
                        </div>

                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                            <div><small>Room</small><div style="font-weight: 500;">${guest.room_id}</div></div>
                            <div><small>Phone</small><div style="font-weight: 500;">${guest.phone}</div></div>
                            <div><small>Check-in</small><div>${guest.checkin_time}</div></div>
                            <div><small>Check-out</small><div>${guest.checkout_time || 'Active'}</div></div>
                        </div>

                        <div style="margin-top: 1rem;">
                            <small>Total Bill</small>
                            <div style="font-size: 1.5rem; font-weight: 700; color: var(--success-color);">₹${(guest.amount || 0) + (guest.extra_charges || 0)}</div>
                        </div>

                        <div style="margin-top: 1rem;">
                            <small>ID Documents</small>
                            <div style="margin-top: 0.5rem;">${photosHtml}</div>
                        </div>
                    </div>

                    <div id="guestEditView" style="display: none;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
                            <h3 style="margin: 0;">Edit Guest Profile</h3>
                            <button type="button" class="close-btn" onclick="toggleGuestEdit(false); return false;" style="padding: 0; font-size: 1.5rem;">×</button>
                        </div>
                        <input type="hidden" id="editGuestOldPhone" value="${guest.phone}">
                        <input type="hidden" id="editGuestBookingId" value="${guest.id}">
                        <div class="form-group">
                            <label>Full Name</label>
                            <input type="text" id="editGuestName" class="form-control" value="${guest.guest_name}">
                        </div>
                        <div class="form-group">
                            <label>Email Address</label>
                            <input type="email" id="editGuestEmail" class="form-control" value="${guestEmail}" placeholder="guest@example.com">
                        </div>
                        <div class="form-group">
                            <label>Phone Number</label>
                            <input type="tel" id="editGuestPhone" class="form-control" value="${guest.phone}">
                        </div>
                        <div class="form-group">
                            <label>Additional Guest Names</label>
                            <div id="editMembersContainer">
                                ${memberNames.map((m, i) => `
                                    <div style="display:flex; gap:6px; margin-bottom:6px;" id="editMemberRow_${i}">
                                        <input type="text" class="form-control edit-member-input" value="${m}" placeholder="Guest name">
                                        <button type="button" onclick="document.getElementById('editMemberRow_${i}').remove()" style="padding:0 10px; background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.4); border-radius:8px; color:#ef4444; cursor:pointer;">✕</button>
                                    </div>`).join('')}
                            </div>
                            <button type="button" onclick="addEditMemberField()" style="margin-top:6px; padding:8px 14px; background:rgba(168,85,247,0.12); border:1px dashed rgba(168,85,247,0.5); border-radius:8px; color:var(--primary-color); cursor:pointer; font-size:0.9rem;">+ Add Guest</button>
                        </div>
                        <div class="form-group">
                            <label>Add / Update ID Photo</label>
                            <input type="file" id="editGuestPhoto" class="form-control" accept="image/*,.pdf" multiple>
                        </div>
                        <div style="display: flex; gap: 10px; margin-top: 1.5rem;">
                            <button type="button" class="btn btn-success" style="flex: 1;" onclick="saveGuestEdit(); return false;">Save Changes</button>
                            <button type="button" class="btn btn-outline" style="flex: 1;" onclick="toggleGuestEdit(false); return false;">Cancel</button>
                        </div>
                    </div>

                    <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 1.5rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
                        <button type="button" class="btn btn-primary" onclick="downloadGuestProfilePdf()">Download PDF</button>
                        <a href="/bill/${guest.id}" target="_blank" class="btn btn-primary">Print Bill</a>
                    </div>
                `;
                document.getElementById('guestProfileModal').classList.add('show');
            } catch (error) { console.error('Error:', error); }
        }

        function downloadGuestProfilePdf() {
            const profileContent = document.getElementById('guestProfileContent');
            if (!profileContent || !window.html2pdf) {
                showAlert('Error', 'PDF export is not available in this browser.', 'error');
                return;
            }

            const contentClone = profileContent.cloneNode(true);
            const hiddenStyles = document.createElement('style');
            hiddenStyles.textContent = `
                body { background: #ffffff; color: #111827; }
                #guestProfileContent { padding: 0; }
                #guestDisplayView, #guestEditView { display: block !important; }
                .btn, .close-btn, .modal-header { display: none !important; }
                .form-group, .form-control, input, label { display: none !important; }
                small { color: #4b5563; }
                h2, h3 { color: #111827; }
                * { box-sizing: border-box; }
            `;
            contentClone.appendChild(hiddenStyles);

            const opt = {
                margin: [0.5, 0.5, 0.5, 0.5],
                filename: `guest-profile-${Date.now()}.pdf`,
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2 },
                jsPDF: { unit: 'in', format: 'a4', orientation: 'portrait' }
            };

            html2pdf().set(opt).from(contentClone).save();
        }

        function toggleGuestEdit(show) {
            const displayView = document.getElementById('guestDisplayView');
            const editView = document.getElementById('guestEditView');
            
            if (!displayView || !editView) {
                console.error('Could not find guestDisplayView or guestEditView');
                return;
            }
            
            displayView.style.display = show ? 'none' : 'block';
            editView.style.display = show ? 'block' : 'none';
            
            // Ensure the modal content is scrolled to top
            if (show) {
                const modalContent = document.querySelector('.modal-content');
                if (modalContent) modalContent.scrollTop = 0;
            }
            
            console.log('Guest edit view toggled:', { show, displayHidden: show, editVisible: show });
        }

        function addEditMemberField(name = '', age = '') {
            const container = document.getElementById('editMembersContainer');
            if (!container) return;
            const idx = Date.now() + Math.random().toString(36).substr(2, 4);
            const div = document.createElement('div');
            div.id = `editMemberRow_${idx}`;
            div.className = 'edit-member-row';
            div.style.cssText = 'display:flex; gap:6px; margin-bottom:6px; align-items:center;';
            div.innerHTML = `
                <input type="text" class="form-control edit-member-name" placeholder="Guest name" value="${name}" style="flex:2;">
                <input type="number" class="form-control edit-member-age" placeholder="Age" min="0" value="${age}" style="width:80px; flex:0 0 80px;">
                <button type="button" onclick="document.getElementById('editMemberRow_${idx}').remove()" style="padding:6px 10px; background:rgba(239,68,68,0.15); border:1px solid rgba(239,68,68,0.4); border-radius:8px; color:#ef4444; cursor:pointer;">✕</button>
            `;
            container.appendChild(div);
        }

        async function saveGuestEdit() {
            const oldPhone = document.getElementById('editGuestOldPhone').value;
            const bookingId = document.getElementById('editGuestBookingId')?.value;
            const name = document.getElementById('editGuestName').value.trim();
            const email = document.getElementById('editGuestEmail').value.trim();
            const phone = document.getElementById('editGuestPhone').value.trim();

            if (!name || !phone) return showAlert('Missing Fields', 'Name and Phone are required', 'warning');

            // Collect member names & ages from edit form
            const memberRows = document.querySelectorAll('.edit-member-row');
            const membersList = [];
            memberRows.forEach(row => {
                const nameInp = row.querySelector('.edit-member-name')?.value.trim();
                const ageInp = row.querySelector('.edit-member-age')?.value.trim();
                if (nameInp) {
                    membersList.push(ageInp ? `${nameInp} (${ageInp})` : nameInp);
                }
            });

            const formData = new FormData();
            formData.append('old_phone', oldPhone);
            formData.append('name', name);
            formData.append('email', email);
            formData.append('phone', phone);
            if (bookingId) formData.append('booking_id', bookingId);
            formData.append('members', JSON.stringify(membersList));

            const fileInput = document.getElementById('editGuestPhoto');
            if (fileInput && fileInput.files) {
                for (let i = 0; i < fileInput.files.length; i++) {
                    formData.append('id_photos', fileInput.files[i]);
                }
            }


            try {
                const response = await fetch('/api/guest/update', {
                    method: 'POST',
                    body: formData
                });
                const result = await response.json();
                if (result.success) {
                    showAlert('Success', 'Guest profile updated successfully', 'success');
                    closeModal('guestProfileModal');
                    loadGuests();
                } else {
                    showAlert('Error', result.message || 'Failed to update profile', 'error');
                }
            } catch (error) {
                console.error('Error saving guest edit:', error);
                showAlert('Error', 'An error occurred while saving', 'error');
            }
        }

        // Guest Search Filter
        function filterGuests() {
            const input = document.getElementById('guestSearchInput');
            if (!input) return;
            const filter = input.value.toUpperCase().trim();
            const table = document.getElementById('guestsTableBody');
            if (!table) return;
            const tr = table.getElementsByTagName('tr');

            for (let i = 0; i < tr.length; i++) {
                const tdName = tr[i].getElementsByTagName('td')[0];
                const tdPhone = tr[i].getElementsByTagName('td')[1];
                const tdRoom = tr[i].getElementsByTagName('td')[2];

                if (tdName && tdPhone && tdRoom) {
                    const txtName = (tdName.textContent || tdName.innerText).toUpperCase();
                    const txtPhone = (tdPhone.textContent || tdPhone.innerText).toUpperCase();
                    const txtRoom = (tdRoom.textContent || tdRoom.innerText).toUpperCase();

                    if (txtName.indexOf(filter) > -1 ||
                        txtPhone.indexOf(filter) > -1 ||
                        txtRoom.indexOf(filter) > -1) {
                        tr[i].style.display = "";
                    } else {
                        tr[i].style.display = "none";
                    }
                }
            }
        }

        // --- Expenses ---
        async function loadExpenses(params = {}) {
            try {
                // Fetch and update summary cards first
                try {
                    const summaryResponse = await fetch('/api/expenses/summary');
                    if (summaryResponse.ok) {
                        const summary = await summaryResponse.json();
                        if (summary.success) {
                            document.getElementById('expenseTotalAllTime').textContent = `₹${summary.total_all_time.toLocaleString()}`;
                            document.getElementById('expenseTotalToday').textContent = `₹${summary.total_today.toLocaleString()}`;
                        }
                    }
                } catch (summaryError) {
                    console.error('Error fetching expense summary:', summaryError);
                }

                let url = '/api/expenses';
                const query = new URLSearchParams(params).toString();
                if (query) url += '?' + query;

                const response = await fetch(url);
                if (!response.ok) throw new Error('Failed to fetch expenses');
                const expenses = await response.json();
                
                // Calculate filtered total
                const filteredTotal = expenses.reduce((sum, exp) => sum + exp.amount, 0);
                document.getElementById('expenseTotalFiltered').textContent = `₹${filteredTotal.toLocaleString()}`;
                
                // Update filtered label based on search range
                const range = document.getElementById('expenseSearchRange').value;
                const label = document.getElementById('expenseFilteredLabel');
                if (label) {
                    if (range === 'daily') label.textContent = 'Filtered Daily Total';
                    else if (range === 'monthly') label.textContent = 'Filtered Monthly Total';
                    else if (range === 'yearly') label.textContent = 'Filtered Yearly Total';
                    else label.textContent = 'Filtered Total (All Time)';
                }

                const container = document.getElementById('expenseList');
                if (!container) return;

                if (expenses.length === 0) {
                    container.innerHTML = '<div style="text-align: center; padding: 2rem; color: var(--text-secondary);">No expenses found for this period.</div>';
                    return;
                }

                container.innerHTML = expenses.map(exp => `
                    <div class="expense-item" style="border-bottom: 1px solid var(--border-color); padding: 10px 0;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <div style="font-weight: 600; color: var(--text-primary);">${exp.name}</div>
                                <div style="font-size: 0.75rem; color: var(--text-secondary);">
                                    ${exp.date} • <span class="badge bg-secondary" style="background:#6c757d; color:white; padding: 2px 5px; border-radius:3px;">${exp.category || 'General'}</span>
                                </div>
                            </div>
                            <div style="font-weight: 700; color: var(--danger-color); font-size: 1.1rem;">-₹${exp.amount.toLocaleString()}</div>
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('Error loading expenses:', error);
            }
        }

        function updateExpenseSearchUI() {
            const range = document.getElementById('expenseSearchRange').value;
            const dateInput = document.getElementById('expenseSearchDate');
            const monthYearGroup = document.getElementById('expenseMonthYearGroup');
            const yearOnlySelect = document.getElementById('expenseSearchYearOnly');

            dateInput.style.display = 'none';
            monthYearGroup.style.display = 'none';
            yearOnlySelect.style.display = 'none';

            if (range === 'daily') dateInput.style.display = 'block';
            else if (range === 'monthly') {
                monthYearGroup.style.display = 'flex';
                populateExpenseYears('expenseSearchYear');
            }
            else if (range === 'yearly') {
                yearOnlySelect.style.display = 'block';
                populateExpenseYears('expenseSearchYearOnly');
            }
        }

        function populateExpenseYears(selectId) {
            const select = document.getElementById(selectId);
            if (!select || select.options.length > 0) return;
            const currentYear = new Date().getFullYear();
            for (let i = currentYear; i >= currentYear - 5; i--) {
                const opt = document.createElement('option');
                opt.value = i;
                opt.textContent = i;
                select.appendChild(opt);
            }
        }

        function runExpenseSearch() {
            const range = document.getElementById('expenseSearchRange').value;
            const params = {};

            if (range === 'daily') {
                const val = document.getElementById('expenseSearchDate').value;
                if (!val) return showAlert('Required', 'Please select a date', 'warning');
                params.date = val;
            } else if (range === 'monthly') {
                params.month = document.getElementById('expenseSearchMonth').value;
                params.year = document.getElementById('expenseSearchYear').value;
            } else if (range === 'yearly') {
                params.year = document.getElementById('expenseSearchYearOnly').value;
            }

            loadExpenses(params);
        }

        async function addExpense() {
            const name = document.getElementById('expenseName').value;
            const amount = document.getElementById('expenseAmount').value;
            const category = document.getElementById('expenseCategory').value;
            const date = document.getElementById('expenseDate').value;

            if (!name || !amount) {
                showAlert('Missing Fields', 'Please enter both name and amount.', 'warning');
                return;
            }

            try {
                const response = await fetch('/api/expenses', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        name: name,
                        amount: parseFloat(amount),
                        category: category,
                        date: date
                    })
                });

                if (!response.ok) {
                    const errorMsg = await response.text();
                    throw new Error(errorMsg || `Server error ${response.status}`);
                }

                const result = await response.json();
                if (result.success) {
                    document.getElementById('expenseName').value = '';
                    document.getElementById('expenseAmount').value = '';
                    document.getElementById('expenseDate').value = new Date().toISOString().split('T')[0];
                    showAlert('Success', 'Expense added successfully!', 'success');
                    loadExpenses();
                    if (window.updateFinancials) updateFinancials();
                } else {
                    showAlert('Error', result.message || 'Failed to add expense', 'error');
                }
            } catch (error) {
                console.error('Error adding expense:', error);
                showAlert('Error', 'Could not add expense: ' + error.message, 'error');
            }
        }

        // --- Calendar ---
        function loadCalendar() {
            setTimeout(() => {
                const calendarEl = document.getElementById('calendar');
                if (!calendarEl) return;
                if (calendarInstance) {
                    calendarInstance.render();
                    return;
                }
                calendarInstance = new FullCalendar.Calendar(calendarEl, {
                    initialView: 'dayGridMonth',
                    headerToolbar: {
                        left: 'prev,next today',
                        center: 'title',
                        right: 'dayGridMonth,timeGridWeek,timeGridDay'
                    },
                    events: '/api/reservations',
                    eventClick: function (info) {
                        showAlert('Booking Details', 'Booking: ' + info.event.title, 'info');
                    }
                });
                calendarInstance.render();
            }, 100);
        }

        // --- System Maintenance ---
        function viewDatabaseAsPdf() {
            window.open('/report/full-database', '_blank');
        }

        async function viewBackup() {
            const fileInput = document.getElementById('backupFile');
            const file = fileInput.files[0];
            
            if (!file) { showAlert('Error', 'Please select a backup zip file first.', 'warning'); return; }
            
            const button = document.querySelector('button[onclick="viewBackup()"]');
            const originalText = button.textContent;
            button.textContent = 'Processing...';
            button.disabled = true;
            
            const formData = new FormData();
            formData.append('backup_zip', file);
            
            try {
                const res = await fetch('/api/backup/view', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                
                button.textContent = originalText;
                button.disabled = false;
                
                if (data.success) {
                    window.open(`/backup_viewer/${data.backup_id}`, '_blank');
                } else {
                    showAlert('Error', data.message || 'Failed to process backup.', 'error');
                }
            } catch (err) {
                button.textContent = originalText;
                button.disabled = false;
                showAlert('Error', 'Network error. Please try again.', 'error');
            }
        }

        // --- Modals & Global events ---
        function closeModal(modalId) {
            const modal = document.getElementById(modalId);
            if (modal) modal.classList.remove('show');
        }

        // Toggle Mobile Menu
        function toggleMenu() {
            const nav = document.querySelector('.header-nav');
            nav.classList.toggle('show');
        }

        // --- Sidebar Refresh Button ---
        function sidebarRefresh() {
            const icon = document.getElementById('refreshIcon');
            const btn  = document.getElementById('sidebarRefreshBtn');
            if (icon) {
                icon.style.transition = 'transform 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
                icon.style.transform  = 'rotate(360deg)';
            }
            if (btn) {
                btn.style.opacity = '0.7';
                btn.disabled = true;
            }
            // Give the spin a moment to show then reload
            setTimeout(() => window.location.reload(), 500);
        }

        // Hover style for refresh button (JS because inline :hover not supported)
        document.addEventListener('DOMContentLoaded', () => {
            const btn = document.getElementById('sidebarRefreshBtn');
            if (btn) {
                btn.addEventListener('mouseenter', () => {
                    btn.style.background = 'rgba(168,85,247,0.25)';
                    btn.style.borderColor = 'var(--primary-color)';
                    btn.style.transform = 'translateY(-1px)';
                    btn.style.boxShadow = '0 4px 12px rgba(168,85,247,0.2)';
                });
                btn.addEventListener('mouseleave', () => {
                    btn.style.background = 'rgba(168,85,247,0.12)';
                    btn.style.borderColor = 'rgba(168,85,247,0.35)';
                    btn.style.transform = 'translateY(0)';
                    btn.style.boxShadow = 'none';
                });
            }
        });

        // Close menu when clicking outside
        window.onclick = (e) => {
            if (e.target.classList.contains('modal')) e.target.classList.remove('show');
            if (!e.target.closest('.header-nav') && !e.target.closest('.mobile-menu-btn')) {
                document.querySelector('.header-nav')?.classList.remove('show');
            }
        };

        // --- Legacy fallback for old global variables ---
        window.showPage = showPage;
        window.loadRooms = loadRooms;
        window.toggleTheme = toggleTheme;
        window.closeModal = closeModal;
        window.addNewRoom = addNewRoom;
        window.confirmOverride = confirmOverride;
        window.openBookingModal = openBookingModal;
        window.openCheckoutModal = openCheckoutModal;
        if (typeof searchGuest !== 'undefined') window.searchGuest = searchGuest;
        window.addExpense = addExpense;
        if (typeof restoreSystem !== 'undefined') window.restoreSystem = restoreSystem;
        window.updateFinancials = updateFinancials;
        window.exportFinancials = () => exportToPDF('financial', 'Financial_Report');
        window.exportToExcel = exportToExcel;
        window.exportToPDF = exportToPDF;
        window.filterGuests = filterGuests;

    

        function openSupportModal() {
            document.getElementById('supportModal').classList.add('show');
        }

        async function submitSupportMessage() {
            const subject = document.getElementById('supportSubject').value;
            const message = document.getElementById('supportMessage').value;

            if (!subject || !message) {
                return showAlert('Required', 'Please fill in both subject and message', 'error');
            }

            try {
                const response = await fetch('/api/hotel/message', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ subject, message })
                });
                const result = await response.json();
                if (result.success) {
                    showAlert('Message Sent', 'Your message has been sent to our support team.', 'success');
                    closeModal('supportModal');
                    document.getElementById('supportSubject').value = '';
                    document.getElementById('supportMessage').value = '';
                } else {
                    showAlert('Error', result.message, 'error');
                }
            } catch (err) {
                showAlert('Error', 'Connection failed', 'error');
            }
        }

        // Close tooltip when clicking outside
        window.addEventListener('click', function (e) {
            if (!e.target.closest('.help-btn') && !e.target.closest('.help-tooltip')) {
                const tooltip = document.getElementById('helpTooltip');
                if (tooltip) tooltip.style.display = 'none';
            }
        });

        // Custom Alert System
        function showCustomAlert(message, title = 'Notification') {
            document.getElementById('alertMessage').innerText = message;
            document.getElementById('alertTitle').innerText = title;
            document.getElementById('customAlert').classList.add('show');
        }

        function closeCustomAlert() {
            document.getElementById('customAlert').classList.remove('show');
        }

        // Override native alert
        window.alert = function (message) {
            };
    

        function openSidebar() {
            const sidebar = document.getElementById('dashSidebar');
            if (sidebar) sidebar.classList.add('open');
            const overlay = document.getElementById('sidebarOverlay');
            if (overlay) overlay.classList.add('show');
        }

        function closeSidebar() {
            const sidebar = document.getElementById('dashSidebar');
            if (sidebar) sidebar.classList.remove('open');
            const overlay = document.getElementById('sidebarOverlay');
            if (overlay) overlay.classList.remove('show');
        }

        // Enhancement for showPage to handle sidebar active state
        if (typeof window.showPage === 'function') {
            const originalShowPage = window.showPage;
            window.showPage = function(pageId, btn) {
                originalShowPage(pageId);
                
                // Update sidebar active states
                if (btn && btn.classList.contains('sidebar-nav-item')) {
                    document.querySelectorAll('.sidebar-nav-item').forEach(item => item.classList.remove('active'));
                    btn.classList.add('active');
                }

                // Auto-close sidebar on mobile after navigation
                if (window.innerWidth <= 900) {
                    closeSidebar();
                }
            };
        }
    

        let portalQRInstance = null;
        let portalURL = '';

        // Load QR code when Guest Portal page is opened
        async function initGuestPortal() {
            try {
                const resp = await fetch('/api/portal/qr-data');
                const data = await resp.json();
                if (data.success) {
                    portalURL = data.url;
                    document.getElementById('qrUrlText').innerText = portalURL;

                    // Generate QR code
                    const container = document.getElementById('qrCodeContainer');
                    container.innerHTML = '';
                    portalQRInstance = new QRCode(container, {
                        text: portalURL,
                        width: 200,
                        height: 200,
                        colorDark: '#0f172a',
                        colorLight: '#ffffff',
                        correctLevel: QRCode.CorrectLevel.H
                    });
                }
            } catch (e) {
                console.error('QR load error:', e);
            }

            loadPortalRequests();
        }

        async function loadPortalRequests() {
            try {
                const resp = await fetch('/api/portal/requests');
                const requests = await resp.json();
                const container = document.getElementById('portalRequestsList');

                if (requests.length === 0) {
                    container.innerHTML = `
                        <div style="text-align: center; color: var(--text-muted); padding: 3rem;">
                            <div style="font-size: 3rem; margin-bottom: 1rem;">📭</div>
                            <p>No requests yet / अभी कोई अनुरोध नहीं</p>
                            <p style="font-size: 0.8rem;">Share the QR code with guests to get started!</p>
                        </div>`;
                    return;
                }

                let html = '';
                requests.forEach(r => {
                    const isPending = r.status === 'pending';
                    const statusColor = r.status === 'accepted' ? '#10b981' : r.status === 'rejected' ? '#ef4444' : '#f59e0b';
                    const statusLabel = r.status === 'accepted' ? '✅ Accepted' : r.status === 'rejected' ? '❌ Rejected' : '⏳ Pending';
                    const photoHtml = r.id_photo ? `<a href="/static/${r.id_photo}" target="_blank" style="color: var(--gold); font-size: 0.8rem; text-decoration: underline;">📷 View ID</a>` : '';

                    html += `
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 14px; padding: 1rem 1.25rem; margin-bottom: 0.75rem; display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;">
                        <div style="flex-shrink: 0; width: 44px; height: 44px; background: rgba(212,175,55,0.15); border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 1.3rem;">👤</div>
                        <div style="flex: 1; min-width: 150px;">
                            <strong style="font-size: 1.05rem;">${r.guest_name}</strong>
                            <div style="color: var(--text-muted); font-size: 0.85rem;">📞 ${r.phone}</div>
                            ${r.address ? `<div style="color: var(--text-muted); font-size: 0.8rem;">📍 ${r.address}</div>` : ''}
                            ${(() => { try { const m = JSON.parse(r.members || '[]'); return m.length > 0 ? `<div style="color: var(--text-muted); font-size: 0.8rem;">👥 Members: ${m.join(', ')}</div>` : ''; } catch(e) { return ''; } })()}
                            ${photoHtml}
                        </div>
                        <div style="font-size: 0.75rem; color: var(--text-muted);">${r.created_at || ''}</div>
                        <div style="display: flex; gap: 0.5rem; align-items: center;">
                            ${isPending ? `
                                <button onclick="openAcceptModal(${r.id}, '${r.guest_name.replace(/'/g, "\\'")}', '${r.phone}')" 
                                    style="padding: 0.5rem 1rem; background: linear-gradient(135deg, #10b981, #059669); color: white; border: none; border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 0.85rem;">
                                    ✅ Accept
                                </button>
                                <button onclick="rejectRequest(${r.id})" 
                                    style="padding: 0.5rem 1rem; background: rgba(239,68,68,0.15); color: #ef4444; border: 1px solid rgba(239,68,68,0.3); border-radius: 10px; cursor: pointer; font-weight: 600; font-size: 0.85rem;">
                                    ❌ Reject
                                </button>
                            ` : `<span style="color: ${statusColor}; font-weight: 600; font-size: 0.85rem;">${statusLabel}</span>`}
                        </div>
                    </div>`;
                });

                container.innerHTML = html;
            } catch (e) {
                console.error('Portal requests error:', e);
            }
        }

        async function openAcceptModal(requestId, guestName, phone) {
            document.getElementById('acceptRequestId').value = requestId;
            document.getElementById('acceptGuestName').innerText = guestName;
            document.getElementById('acceptGuestPhone').innerText = '📞 ' + phone;

            // Set default check-in time to now
            const now = new Date();
            const localISO = new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
            document.getElementById('acceptCheckinTime').value = formatAmPmDateTime(localISO);

            // Load available rooms into cache
            try {
                const resp = await fetch('/api/rooms');
                window._availableRooms = (await resp.json()).filter(r => r.status === 'available');
            } catch (e) {
                window._availableRooms = [];
                console.error('Rooms load error:', e);
            }

            // Reset room rows to one default
            document.getElementById('roomRowsContainer').innerHTML = '';
            addRoomRow();

            document.getElementById('acceptCheckinModal').classList.add('show');
        }

        function closeAcceptModal() {
            document.getElementById('acceptCheckinModal').classList.remove('show');
        }

        function buildRoomOptions() {
            const rooms = window._availableRooms || [];
            let opts = '<option value="">Select Room / कमरा चुनें</option>';
            rooms.forEach(r => {
                opts += `<option value="${r.room_id}">🚪 Room ${r.room_id} ${r.room_type ? '(' + r.room_type + ')' : ''}</option>`;
            });
            return opts;
        }

        let _roomRowCount = 0;
        function addRoomRow() {
            _roomRowCount++;
            const id = _roomRowCount;
            const container = document.getElementById('roomRowsContainer');
            const row = document.createElement('div');
            row.id = `roomRow_${id}`;
            row.style.cssText = 'display:grid; grid-template-columns: 1fr 1fr auto; gap: 0.75rem; align-items: center; margin-bottom: 0.75rem; background: rgba(255,255,255,0.03); padding: 0.75rem; border-radius: 10px; border: 1px solid var(--border-color);';
            row.innerHTML = `
                <select class="form-control room-row-select" data-row="${id}" style="padding: 0.6rem;">${buildRoomOptions()}</select>
                <input type="number" class="form-control room-row-price" data-row="${id}" placeholder="Price ₹" style="padding: 0.6rem;">
                ${id > 1 ? `<button type="button" onclick="removeRoomRow(${id})" style="background: rgba(239,68,68,0.15); color:#ef4444; border:1px solid rgba(239,68,68,0.3); border-radius:8px; padding:6px 10px; cursor:pointer; font-size:1rem; white-space:nowrap;">✕</button>` : '<span></span>'}
            `;
            container.appendChild(row);
        }

        function removeRoomRow(id) {
            const row = document.getElementById(`roomRow_${id}`);
            if (row) row.remove();
        }

        async function confirmAcceptCheckin() {
            const requestId = document.getElementById('acceptRequestId').value;
            const checkinTime = parseAmPmDateTime(document.getElementById('acceptCheckinTime').value);
            const checkoutTime = parseAmPmDateTime(document.getElementById('acceptCheckoutTime').value);

            // Collect all room rows
            const selects = document.querySelectorAll('.room-row-select');
            const prices = document.querySelectorAll('.room-row-price');
            const roomEntries = [];
            let hasError = false;

            selects.forEach((sel, idx) => {
                const roomId = sel.value;
                const amount = prices[idx] ? prices[idx].value : '';
                if (!roomId) {
                    showAlert('Error', 'Please select a room for each row / सभी पंक्तियों के लिए कमरा चुनें', 'error');
                    hasError = true;
                    return;
                }
                if (!amount) {
                    showAlert('Error', 'Please enter price for each room / सभी कमरों का किराया दर्ज करें', 'error');
                    hasError = true;
                    return;
                }
                roomEntries.push({ room_id: roomId, amount: parseFloat(amount) });
            });

            if (hasError || roomEntries.length === 0) return;

            try {
                // Check in each room sequentially
                let allOk = true;
                for (let i = 0; i < roomEntries.length; i++) {
                    const resp = await fetch('/api/portal/accept', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            request_id: parseInt(requestId),
                            room_id: roomEntries[i].room_id,
                            amount: roomEntries[i].amount,
                            checkin_time: checkinTime,
                            checkout_time: checkoutTime,
                            // only mark request as accepted on last room
                            is_last: i === roomEntries.length - 1
                        })
                    });
                    const result = await resp.json();
                    if (!result.success) {
                        showAlert('Error', result.message || `Failed to check in Room ${roomEntries[i].room_id}`, 'error');
                        allOk = false;
                        break;
                    }
                }

                if (allOk) {
                    closeAcceptModal();
                    const roomList = roomEntries.map(r => 'Room ' + r.room_id).join(', ');
                    showAlert('Success! / सफल!', `Guest checked into ${roomList} successfully!`, 'success');
                    loadPortalRequests();
                    if (typeof loadRooms === 'function') loadRooms();
                }
            } catch (e) {
                showAlert('Error', 'Connection error / कनेक्शन त्रुटि', 'error');
            }
        }

        async function rejectRequest(requestId) {
            if (!confirm('Reject this request? / क्या आप इस अनुरोध को अस्वीकार करना चाहते हैं?')) return;

            try {
                const resp = await fetch('/api/portal/reject', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ request_id: requestId })
                });
                const result = await resp.json();
                if (result.success) {
                    loadPortalRequests();
                }
            } catch (e) {
                console.error('Reject error:', e);
            }
        }

        function downloadQR() {
            const canvas = document.querySelector('#qrCodeContainer canvas');
            if (canvas) {
                const link = document.createElement('a');
                link.download = 'guest-checkin-qr.png';
                link.href = canvas.toDataURL('image/png');
                link.click();
            }
        }

        function copyQRLink() {
            if (portalURL) {
                navigator.clipboard.writeText(portalURL).then(() => {
                    showAlert('Copied! / कॉपी हो गया!', 'Link copied to clipboard', 'success');
                }).catch(() => {
                    // Fallback
                    const ta = document.createElement('textarea');
                    ta.value = portalURL;
                    document.body.appendChild(ta);
                    ta.select();
                    document.execCommand('copy');
                    document.body.removeChild(ta);
                    showAlert('Copied!', 'Link copied', 'success');
                });
            }
        }

        // Poll pending count for badge
        async function updatePortalBadge() {
            try {
                const resp = await fetch('/api/portal/pending-count');
                const data = await resp.json();
                const badge = document.getElementById('portalBadge');
                if (badge) {
                    if (data.count > 0) {
                        badge.style.display = 'inline-block';
                        badge.innerText = data.count;
                    } else {
                        badge.style.display = 'none';
                    }
                }
            } catch (e) { /* silent */ }
        }

        // Hook into showPage to initialize portal when opened
        const _origShowPageForPortal = window.showPage;
        window.showPage = function(pageId, btn) {
            if (typeof _origShowPageForPortal === 'function') {
                _origShowPageForPortal(pageId, btn);
            }
            if (pageId === 'guest-portal') {
                initGuestPortal();
            }
        };

        // Start badge polling
        updatePortalBadge();
        setInterval(updatePortalBadge, 15000);
    