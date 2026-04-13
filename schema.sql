-- ============================================================
--  RESCUE — Database Schema
--  Run: mysql -u root -p < schema.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS rescue_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE rescue_db;

-- ─────────────────────────────────────────
--  HOSPITALS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hospitals (
    id          INT          PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(255) NOT NULL,
    location    VARCHAR(255) NOT NULL,
    network     ENUM('5G','4G','3G') DEFAULT '5G',
    status      ENUM('online','offline','maintenance') DEFAULT 'online',
    icu_capacity INT DEFAULT 0,
    icu_available INT DEFAULT 0,
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

-- ─────────────────────────────────────────
--  USERS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id          INT          PRIMARY KEY AUTO_INCREMENT,
    username    VARCHAR(100) NOT NULL UNIQUE,
    email       VARCHAR(255) NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,
    role        ENUM('admin','staff') NOT NULL DEFAULT 'staff',
    hospital_id INT          NULL,
    created_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE SET NULL
);

-- ─────────────────────────────────────────
--  RESOURCES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS resources (
    id          INT          PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(255) NOT NULL,
    category    ENUM('drug','equipment','bed','blood','other') DEFAULT 'other',
    hospital_id INT          NOT NULL,
    stock       INT          NOT NULL DEFAULT 0,
    unit        VARCHAR(50)  DEFAULT 'units',
    critical_threshold INT  DEFAULT 5,
    updated_at  TIMESTAMP    DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE CASCADE
);

-- ─────────────────────────────────────────
--  TRANSFERS
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transfers (
    id               INT  PRIMARY KEY AUTO_INCREMENT,
    from_hospital_id INT  NOT NULL,
    to_hospital_id   INT  NOT NULL,
    resource_id      INT  NOT NULL,
    units            INT  NOT NULL DEFAULT 1,
    status           ENUM('pending','approved','rejected','completed') DEFAULT 'pending',
    requested_by     INT  NOT NULL,
    approved_by      INT  NULL,
    notes            TEXT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (from_hospital_id) REFERENCES hospitals(id),
    FOREIGN KEY (to_hospital_id)   REFERENCES hospitals(id),
    FOREIGN KEY (resource_id)      REFERENCES resources(id),
    FOREIGN KEY (requested_by)     REFERENCES users(id),
    FOREIGN KEY (approved_by)      REFERENCES users(id) ON DELETE SET NULL
);

-- ─────────────────────────────────────────
--  MESSAGES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id          INT       PRIMARY KEY AUTO_INCREMENT,
    sender_id   INT       NOT NULL,
    content     TEXT      NOT NULL,
    broadcast   TINYINT(1) DEFAULT 1,
    to_hospital INT       NULL,
    timestamp   DATETIME  DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id)   REFERENCES users(id),
    FOREIGN KEY (to_hospital) REFERENCES hospitals(id) ON DELETE SET NULL
);

-- ─────────────────────────────────────────
--  AMBULANCES
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ambulances (
    id          INT         PRIMARY KEY AUTO_INCREMENT,
    code        VARCHAR(50) NOT NULL UNIQUE,
    hospital_id INT         NULL,
    status      ENUM('active','busy','offline') DEFAULT 'active',
    location    VARCHAR(255) DEFAULT 'Base',
    eta         VARCHAR(50)  DEFAULT '--',
    updated_at  TIMESTAMP   DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id) ON DELETE SET NULL
);

-- ─────────────────────────────────────────
--  TRIAGE
-- ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS triage (
    id           INT  PRIMARY KEY AUTO_INCREMENT,
    case_code    VARCHAR(20) UNIQUE,
    hospital_id  INT  NOT NULL,
    patient_anon VARCHAR(100),
    condition_name VARCHAR(255),
    priority     ENUM('P1','P2','P3') DEFAULT 'P2',
    status       ENUM('active','stable','discharged') DEFAULT 'active',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (hospital_id) REFERENCES hospitals(id)
);

-- ============================================================
--  SAMPLE DATA
-- ============================================================

-- Hospitals
INSERT INTO hospitals (id, name, location, network, status, icu_capacity, icu_available) VALUES
(1, 'KEM Hospital',               'Parel, South Mumbai',     '5G', 'online', 342, 87),
(2, 'Hinduja Hospital',           'Mahim, Mumbai',           '5G', 'online', 220, 54),
(3, 'Kokilaben Dhirubhai Ambani', 'Andheri West, Mumbai',    '5G', 'online', 310, 120)
ON DUPLICATE KEY UPDATE name=VALUES(name);

-- Users  (passwords are hashed in app.py on first run — see seed_users())
-- Raw passwords: admin=admin123, staff1=staff123, staff2=staff123
-- These get inserted by db.py seed function with proper hashes

-- Resources
INSERT INTO resources (name, category, hospital_id, stock, unit, critical_threshold) VALUES
('ICU Bed',          'bed',       1, 87,  'beds',  10),
('Ventilator',       'equipment', 1, 14,  'units',  3),
('Oxygen Cylinder',  'equipment', 1,  6,  'units',  5),
('Remdesivir',       'drug',      1, 45,  'vials',  8),
('Blood O+',         'blood',     1, 12,  'units',  5),
('ICU Bed',          'bed',       2, 54,  'beds',  10),
('Defibrillator',    'equipment', 2,  8,  'units',  2),
('Insulin',          'drug',      2, 200, 'vials', 20),
('Plasma Units',     'blood',     2,  7,  'units',  3),
('ICU Bed',          'bed',       3,120,  'beds',  15),
('Pembrolizumab',    'drug',      3, 18,  'vials',  4),
('Cardiac Monitor',  'equipment', 3, 22,  'units',  4),
('Dialysis Machine', 'equipment', 3,  5,  'units',  2)
ON DUPLICATE KEY UPDATE stock=VALUES(stock);

-- Ambulances
INSERT INTO ambulances (code, hospital_id, status, location, eta) VALUES
('MH-001', 1, 'active', 'KEM Base',         '--'),
('MH-002', 1, 'busy',   'KEM -> Hinduja',   '8 min'),
('MH-003', 2, 'active', 'Hinduja Base',     '--'),
('MH-004', 2, 'busy',   'Hinduja -> Andheri','12 min'),
('MH-005', 3, 'offline','Maintenance Depot','--')
ON DUPLICATE KEY UPDATE status=VALUES(status);
