/**
 * rescue_api.js
 * Reusable API client for RESCUE frontend.
 * Include in any page: <script src="/static/js/rescue_api.js"></script>
 *
 * ─────────────────────────────────────────────────────────
 *  USAGE EXAMPLES  (copy-paste these anywhere you need them)
 * ─────────────────────────────────────────────────────────
 */

// ─── BASE CLIENT ───────────────────────────────────────────
const RescueAPI = {
    _call: async (method, url, body = null) => {
        const opts = {
            method,
            headers: { 'Content-Type': 'application/json' },
        };
        if (body) opts.body = JSON.stringify(body);
        const res  = await fetch(url, opts);
        const data = await res.json();
        if (!data.success) throw new Error(data.error || 'API error');
        return data.data;
    },
    get:    (url)        => RescueAPI._call('GET',    url),
    post:   (url, body)  => RescueAPI._call('POST',   url, body),
    put:    (url, body)  => RescueAPI._call('PUT',    url, body),
    delete: (url)        => RescueAPI._call('DELETE', url),
};

// ─── AUTH ──────────────────────────────────────────────────

/**
 * LOGIN EXAMPLE
 * const result = await RescueAPI.login('admin', 'admin123');
 * window.location.href = result.redirect;   // '/admin' or '/staff'
 */
RescueAPI.login = (username, password) =>
    RescueAPI.post('/api/login', { username, password });

/**
 * LOGOUT EXAMPLE
 * await RescueAPI.logout();
 * window.location.href = '/login';
 */
RescueAPI.logout = () => RescueAPI.post('/api/logout', {});

/**
 * CURRENT USER EXAMPLE
 * const me = await RescueAPI.me();
 * console.log(me.role, me.hospital_id);
 */
RescueAPI.me = () => RescueAPI.get('/api/me');

// ─── ADMIN STATS ───────────────────────────────────────────

/**
 * GET DASHBOARD STATS (admin only)
 * const stats = await RescueAPI.stats();
 * document.getElementById('icu').textContent = stats.total_icu;
 */
RescueAPI.stats = () => RescueAPI.get('/api/admin/stats');

// ─── HOSPITALS ─────────────────────────────────────────────

/**
 * LIST ALL HOSPITALS
 * const hospitals = await RescueAPI.hospitals.list();
 * hospitals.forEach(h => console.log(h.name, h.icu_available));
 */
RescueAPI.hospitals = {
    list:   ()        => RescueAPI.get('/api/hospitals'),
    create: (data)    => RescueAPI.post('/api/hospitals', data),
    update: (id, data)=> RescueAPI.put(`/api/hospitals/${id}`, data),
    delete: (id)      => RescueAPI.delete(`/api/hospitals/${id}`),
};

// ─── RESOURCES ─────────────────────────────────────────────

/**
 * LIST RESOURCES (staff sees only their hospital automatically)
 * const resources = await RescueAPI.resources.list();
 *
 * FILTER BY HOSPITAL (admin only)
 * const kem = await RescueAPI.resources.list(1);  // hospital_id = 1
 */
RescueAPI.resources = {
    list:   (hospitalId) => RescueAPI.get('/api/resources' + (hospitalId ? `?hospital_id=${hospitalId}` : '')),
    create: (data)       => RescueAPI.post('/api/resources', data),
    update: (id, data)   => RescueAPI.put(`/api/resources/${id}`, data),
    delete: (id)         => RescueAPI.delete(`/api/resources/${id}`),
};

// ─── TRANSFERS ─────────────────────────────────────────────

/**
 * LIST TRANSFERS
 * const transfers = await RescueAPI.transfers.list();
 *
 * REQUEST A TRANSFER (staff)
 * await RescueAPI.transfers.request({
 *   from_hospital_id: 1,
 *   to_hospital_id:   2,
 *   resource_id:      3,
 *   units:            5,
 *   notes:            'Urgent — patient critical'
 * });
 *
 * APPROVE / REJECT (admin)
 * await RescueAPI.transfers.updateStatus(7, 'approved');
 * await RescueAPI.transfers.updateStatus(7, 'rejected');
 */
RescueAPI.transfers = {
    list:         ()          => RescueAPI.get('/api/transfers'),
    request:      (data)      => RescueAPI.post('/api/transfers', data),
    updateStatus: (id, status)=> RescueAPI.put(`/api/transfers/${id}`, { status }),
};

// ─── MESSAGES ──────────────────────────────────────────────

/**
 * GET ALL MESSAGES
 * const msgs = await RescueAPI.messages.list();
 * msgs.forEach(m => console.log(m.sender_name, m.content, m.timestamp));
 *
 * SEND BROADCAST
 * await RescueAPI.messages.send('KEM: ICU bed available for transfer');
 *
 * SEND DIRECT (to specific hospital)
 * await RescueAPI.messages.send('Need 5 ventilators', false, 2);
 */
RescueAPI.messages = {
    list: () => RescueAPI.get('/api/messages'),
    send: (content, broadcast = true, toHospital = null) =>
        RescueAPI.post('/api/messages', { content, broadcast: broadcast ? 1 : 0, to_hospital: toHospital }),
};

// ─── AMBULANCES ────────────────────────────────────────────

/**
 * LIST AMBULANCES
 * const ambs = await RescueAPI.ambulances.list();
 * ambs.filter(a => a.status === 'active').forEach(a => console.log(a.code));
 */
RescueAPI.ambulances = {
    list:   ()         => RescueAPI.get('/api/ambulances'),
    create: (data)     => RescueAPI.post('/api/ambulances', data),
    update: (id, data) => RescueAPI.put(`/api/ambulances/${id}`, data),
};

// ─── USERS (admin only) ────────────────────────────────────

/**
 * LIST USERS
 * const users = await RescueAPI.users.list();
 *
 * CREATE STAFF ACCOUNT
 * await RescueAPI.users.create({
 *   username:    'staff3',
 *   email:       'staff3@kokilaben.in',
 *   password:    'securepass',
 *   role:        'staff',
 *   hospital_id: 3
 * });
 */
RescueAPI.users = {
    list:   ()      => RescueAPI.get('/api/users'),
    create: (data)  => RescueAPI.post('/api/users', data),
    delete: (id)    => RescueAPI.delete(`/api/users/${id}`),
};

// ─── TRIAGE ────────────────────────────────────────────────

/**
 * GET TRIAGE CASES
 * const cases = await RescueAPI.triage.list();
 *
 * ADD CASE
 * await RescueAPI.triage.add({ patient_anon: '45M', condition_name: 'Cardiac', priority: 'P1' });
 */
RescueAPI.triage = {
    list: ()      => RescueAPI.get('/api/triage'),
    add:  (data)  => RescueAPI.post('/api/triage', data),
};

// ─── CONVENIENCE: POPULATE A DASHBOARD TABLE ───────────────

/**
 * FULL EXAMPLE — Render resources into a <tbody id="resBody">
 *
 * async function loadResources() {
 *   const resources = await RescueAPI.resources.list();
 *   const tbody = document.getElementById('resBody');
 *   tbody.innerHTML = resources.map(r => `
 *     <tr>
 *       <td>${r.name}</td>
 *       <td>${r.stock} ${r.unit}</td>
 *       <td class="${r.stock <= r.critical_threshold ? 'critical' : 'ok'}">
 *         ${r.stock <= r.critical_threshold ? 'CRITICAL' : 'OK'}
 *       </td>
 *     </tr>
 *   `).join('');
 * }
 * loadResources();
 *
 * FULL EXAMPLE — Request a transfer on button click
 *
 * document.getElementById('reqBtn').addEventListener('click', async () => {
 *   try {
 *     await RescueAPI.transfers.request({
 *       from_hospital_id: 1,
 *       to_hospital_id:   2,
 *       resource_id:      5,
 *       units:            3,
 *     });
 *     alert('Transfer requested!');
 *   } catch (e) {
 *     alert('Error: ' + e.message);
 *   }
 * });
 */

// Export for module environments
if (typeof module !== 'undefined') module.exports = RescueAPI;
