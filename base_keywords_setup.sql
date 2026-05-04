-- Run this SQL in your phpMyAdmin / MySQL under the `iitbnf_troubleshooting` database

CREATE TABLE IF NOT EXISTS `complaint_base_keywords` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `keyword` varchar(100) NOT NULL,
  `type` int(11) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `keyword_UNIQUE` (`keyword`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert the default base keywords
INSERT IGNORE INTO `complaint_base_keywords` (`keyword`, `type`) VALUES
('equipment', 1), ('instrument', 1), ('device', 1), ('tool', 1), ('repair', 1), ('maintenance', 1), ('machine', 1), ('broken', 1), ('malfunction', 1),
('ac', 2), ('air conditioning', 2), ('hvac', 2), ('ahu', 2), ('chiller', 2), ('dg set', 2), ('ups', 2), ('generator', 2), ('blower', 2), ('dehumidifier', 2),
('fire', 3), ('smoke', 3), ('hazard', 3), ('safety', 3), ('accident', 3), ('emergency', 3), ('spill', 3), ('gas leak', 3), ('alarm', 3), ('detector', 3),
('process', 4), ('recipe', 4), ('parameter', 4), ('wafer', 4), ('yield', 4), ('sop', 4), ('uniformity', 4), ('contamination', 4),
('salary', 5), ('payroll', 5), ('leave', 5), ('attendance', 5), ('holiday', 5), ('hr', 5), ('reimbursement', 5), ('appraisal', 5), ('promotion', 5), ('office', 5), ('recruitment', 5), ('letter', 5),
('laptop', 6), ('computer', 6), ('printer', 6), ('wifi', 6), ('internet', 6), ('network', 6), ('vpn', 6), ('email', 6), ('password', 6), ('software', 6), ('login', 6), ('usb', 6), ('mouse', 6), ('keyboard', 6),
('purchase', 7), ('procurement', 7), ('order', 7), ('vendor', 7), ('supplier', 7), ('invoice', 7), ('quote', 7), ('chemical', 7), ('consumable', 7), ('spare', 7),
('training', 8), ('workshop', 8), ('course', 8), ('seminar', 8), ('certification', 8), ('orientation', 8), ('session', 8),
('inventory', 9), ('stock', 9), ('missing item', 9), ('spare parts', 9), ('shortage', 9), ('out of stock', 9), ('reorder', 9), ('asset', 9),
('admin', 10), ('permission', 10), ('access', 10), ('approval', 10), ('policy', 10), ('document', 10), ('gate pass', 10), ('certificate', 10), ('noc', 10);
