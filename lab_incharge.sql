-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: Feb 09, 2026 at 10:26 AM
-- Server version: 10.4.28-MariaDB
-- PHP Version: 8.2.4

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `slotbooking`
--

-- --------------------------------------------------------

--
-- Table structure for table `lab_incharge`
--

CREATE TABLE `lab_incharge` (
  `location` varchar(255) NOT NULL,
  `memberid` varchar(255) NOT NULL,
  `faculty_incharge` varchar(255) NOT NULL,
  `locationid` int(11) NOT NULL,
  `permission_req` int(11) NOT NULL,
  `status` smallint(1) NOT NULL
) ENGINE=MyISAM DEFAULT CHARSET=latin1 COLLATE=latin1_swedish_ci;

--
-- Dumping data for table `lab_incharge`
--

INSERT INTO `lab_incharge` (`location`, `memberid`, `faculty_incharge`, `locationid`, `permission_req`, `status`) VALUES
('Micro1 Lab', '2527,699,2268,1173', '', 16, 0, 0),
('AMAT Lab', '699,928', '', 1, 1, 1),
('Nano Lab', '2527,189,699,95', '', 19, 0, 0),
('Nano Litho Lab', '2527,699,95,928', '', 20, 0, 0),
('Micro2 Lab', '2527,189,699,2514', '', 18, 0, 0),
('Wet Chemistry lab', '2527,699,1173,2177', '', 6, 0, 0),
('Bio Sensors Lab (NanoE bldg, 7th floor)', '2527,699,928,2177', '2413,44,155,145', 5, 1, 0),
('Nanoelectronics Processing Lab (NanoE bldg, 1st floor)', '2527,699,928,2177,1779', '', 21, 0, 0),
('EC Lab', '2527,699,2268,1173', '1988,178', 10, 1, 0),
('Micro1 Yellow Room', '2527,2268,928', '', 17, 0, 0),
('Char Lab-2', '699,1586', '45', 7, 0, 1),
('MBE Clean Room 2 (NanoE bldg, Gr floor)', '2527,699,2268,928', '122,1,178', 14, 1, 0),
('Applied Quantum Mechanics Lab 3(NanoE bldg, 5th floor)', '2527,699,2000,1907', '178', 4, 1, 0),
('Applied Quantum Mechanics Lab 2(NanoE bldg, 5th floor)', '2527,699', '45', 3, 1, 0),
('Device Characterization Lab(DC)(NanoE bldg, 3rd Floor)', '2527,699,2378', '1,44,173', 9, 1, 0),
('MBE Clean Room 1 (NanoE bldg, Gr floor)', '2527,699', '122,1,178', 13, 1, 0),
('Hybrid Solar Cells Lab, EE annex', '', '261', 24, 1, 1),
('NCPRE Fab lab (NanoE bldg, 2nd floor)', '', '', 23, 0, 1),
('NCPRE Char lab (NanoE bldg, 3rd floor)', '', '', 22, 0, 1),
('7.1 Lab', '2527,699,928,2177', '44,145', 8, 1, 0),
('Applied Quantum Mechanics Lab 1(NanoE bldg, 5th floor)', '2527,699,2000,2233', '45', 2, 1, 0),
('MCL Lab', '2527,699', '1988', 15, 1, 0),
('Lab for computational Nanotechnology(NanoE bldg, 4th Floor)', '', '493', 12, 0, 1),
('Integrated Systems Lab', '', '46', 11, 1, 0),
('Opto electronics material and devices lab', '1381', '1037', 25, 0, 1),
('Exploration Centre, AMAT', '', '', 26, 0, 1),
('Facility', '', '', 27, 0, 1),
('Discarded', '', '', 28, 0, 1),
('NMPF Lab', '2527,189,699,95', '44,145', 29, 1, 0),
('Transferred to BSBE (through the EE Dept)', '', '', 33, 0, 1),
('Spintronics Lab', '2527,699', '118', 30, 1, 0),
('2D Materials and Devices Lab', '2527,699,2149,1991', '44', 31, 1, 0),
('PPMS Lab', '2527,699', '118', 32, 1, 0),
('Packed & stored in old LN2 plant room (Micro1)', '', '', 34, 0, 1),
('Shifted to DESE Lab, Transit building', '', '', 35, 0, 1),
('Dark room of Char Lab-2', '', '', 36, 0, 1),
('Shifted to NCPRE Module lab', '', '', 37, 0, 1),
('Spectroscopy Lab', '1829', '45', 38, 1, 0),
('Nano 2 Lab', '2527,699,95,2514', '45', 39, 0, 0),
('Testingg', '2249,981', '776,53,43', 40, 0, 1),
('1.1 Service Corridor', '', '', 41, 0, 1),
('Micro-1 outside Area', '', '', 42, 0, 1),
('MYR outside Area', '', '', 43, 0, 1),
('Micro-2 AHU room', '', '', 44, 0, 1),
('Micro-2 Outside Area', '', '', 45, 0, 1),
('Dyna Cool Lab', '', '', 46, 0, 1),
('Nano Service Corridor', '', '', 47, 0, 1),
('Nano Main Corridor', '', '', 48, 0, 1),
('Nano UPS room', '', '', 49, 0, 1),
('Nano AHU room', '', '', 50, 0, 1),
('Nano Outside Area', '', '', 51, 0, 1),
('DG SET Area', '', '', 52, 0, 1),
('CDA Plant Room', '', '', 53, 0, 1),
('CDA Compressor Room', '', '', 54, 0, 1),
('NB Electrical Panel Area', '', '', 55, 0, 1),
('NB UPS Room', '', '', 56, 0, 1),
('NB AHU Room', '', '', 57, 0, 1),
('BMS Room', '', '', 58, 0, 1),
('1.1 Lab', '', '', 59, 0, 1),
('1.2 Lab', '', '', 60, 0, 1),
('MCL Server Room', '', '', 61, 0, 1),
('G.1 Service Corridor', '', '', 62, 0, 1),
('G.2 Service Corridor', '', '', 63, 0, 1),
('G.1 Corridor', '', '', 64, 0, 1),
('G.2 Corridor', '', '', 65, 0, 1),
('G.1 Lab Emergency Exit Door', '', '', 66, 0, 1),
('G.2 Lab Emergency Exit Door', '', '', 67, 0, 1),
('MBE Lab Main Door Entrance', '', '', 68, 0, 1),
('MBE AHU Area', '', '', 69, 0, 1),
('MBE Pass Box Area', '', '', 70, 0, 1),
('MBE Gowning Area', '', '', 71, 0, 1),
('MBE Air Shower', '', '', 72, 0, 1),
('MBE Storage Area', '', '', 73, 0, 1),
('NANO Litho Service Corridor', '', '', 74, 0, 1),
('Nano 1 lab Emergency Exit Door', '', '', 75, 0, 1),
('Nano Lab Emergency Exit Door', '', '', 76, 0, 1),
('G.2 Flip Chip Bonder', '', '', 77, 0, 1),
('Nano 1 Service Corridor', '', '', 78, 0, 1),
('Nano 1 Corridor', '', '', 79, 0, 1),
('Nano Litho Lab Emergency Exit Door', '', '', 80, 0, 1),
('Nano Lab Main Door Entrance', '', '', 81, 0, 1),
('Nano  AHU Area', '', '', 82, 0, 1),
('Nano 1 Pass Box Area', '', '', 83, 0, 1),
('Nano Gowning Area', '', '', 84, 0, 1),
('Nano Litho  Pass Box Area', '', '', 85, 0, 1),
('Nano Litho  Air Shower', '', '', 86, 0, 1),
('Nano 2 Service Corridor - DRIE Transformer', '', '', 87, 0, 1),
('Nano 2 Service Corridor - VOYAGER Pumps, etc', '', '', 88, 0, 1),
('Nano 2 Corridor Emergency Exit Door', '', '', 89, 0, 1),
('Nano 2  Corridor', '', '', 90, 0, 1),
('Nano 2 Lab Emergency Exit Door', '', '', 91, 0, 1),
('Nano AHU Area', '', '', 92, 0, 1),
('Nano Litho Pass Box Area', '', '', 93, 0, 1),
('M-2 Corridor', '', '', 94, 0, 1),
('M-2 Main Entrance', '', '', 95, 0, 1),
('M-2 Emergency Exit Door', '', '', 96, 0, 1),
('M-2 Service Corridor', '', '', 97, 0, 1),
('M-2 PIII Gas Cabinet Area', '', '', 98, 0, 1),
('M-2 HWCVD Toxic Gas Room', '', '', 99, 0, 1),
('M-2 HSK Staff Sitting Area', '', '', 100, 0, 1),
('NCPRE Fab (2.1) Main Corridor Entrance', '', '', 101, 0, 1),
('NCPRE Fab (2.2) Main Corridor Emergency Exit', '', '', 102, 0, 1),
('NCPRE Gowning Area', '', '', 103, 0, 1),
('NCPRE Air Shower', '', '', 104, 0, 1),
('NCPRE (2.1)', '', '', 105, 0, 1),
('2.2 - Lab Emergency Exit', '', '', 106, 0, 1),
('2.1 - Near 4TEBE', '', '', 107, 0, 1),
('2.1 - Near Ellipsometer', '', '', 108, 0, 1),
('2.1 - Near Furnace / Passbox', '', '', 109, 0, 1),
('M-1 Corridor', '', '', 110, 0, 1),
('Old Chemistry Room', '', '', 111, 0, 1),
('Dicer Room', '', '', 112, 0, 1),
('Micro UPS room', '', '', 113, 0, 1),
('Chemical Storage Room', '1173,1779,2514', '1', 114, 1, 0),
('M-1 lab Main Door Entrance', '', '', 115, 0, 1),
('M-1 Lab Emergency Exit Window', '', '', 116, 0, 1),
('1.1 Lab Corridor', '', '', 117, 0, 1),
('1.1 Lab Gowning Area', '', '', 118, 0, 1),
('1.1 Lab Emergency Exit', '', '', 119, 0, 1),
('1.2 Lab Emergency Exit', '', '', 120, 0, 1),
('MYR Gowning Area', '', '', 121, 0, 1),
('MYR AHU Room', '', '', 122, 0, 1),
('MYR Service Corridor', '', '', 123, 0, 1),
('MYR Emergency Exit Door', '', '', 124, 0, 1),
('MYR Door Entrance', '', '', 125, 0, 1),
('MYR AHU ODU Area', '', '', 126, 0, 1),
('3.2 Lab', '', '', 127, 0, 1),
('Near NB Attendance PC', '', '', 128, 0, 1),
('Near Main Lift Side Wall', '', '', 129, 0, 1),
('Near Service Lift Side Wall', '', '', 130, 0, 1),
('MBE Service Corridor Fire Panel', '', '', 131, 0, 1),
('MBE service corridor fire panel ahu side', '', '', 132, 0, 1),
('1st flr Near store room entrance door', '', '', 133, 0, 1),
('1st flr Near main lift side wall', '', '', 134, 0, 1),
('1st flr Near service lift side wall', '', '', 135, 0, 1),
('1.1 service corridor fire panel', '', '', 136, 0, 1),
('1.2 service corridor fire panel', '', '', 137, 0, 1),
('2nd flr Near main lift side wall', '', '', 138, 0, 1),
('2nd flr Near service lift side wall', '', '', 139, 0, 1),
('2nd flr service corridor fire panel', '', '', 140, 0, 1),
('3rd flr Near main lift side wall', '', '', 141, 0, 1),
('3rd flr Near service lift side wall', '', '', 142, 0, 1),
('3.1 corridor fire panel', '', '', 143, 0, 1),
('3.2 corridor fire panel', '', '', 144, 0, 1),
('3.3 corridor fire panel', '', '', 145, 0, 1),
('4th flr Near main lift side wall', '', '', 146, 0, 1),
('4th flr Near service lift side wall', '', '', 147, 0, 1),
('5th flr Near main lift side wall', '', '', 148, 0, 1),
('5th flr Near service lift side wall', '', '', 149, 0, 1),
('6th flr Near main lift side wall', '', '', 150, 0, 1),
('6th flr Near service lift side wall', '', '', 151, 0, 1),
('7th flr Near main lift side wall', '', '', 152, 0, 1),
('7th flr Near service lift side wall', '', '', 153, 0, 1),
('7th flr main corridor', '', '', 154, 0, 1),
('M1 near entrance door', '', '', 155, 0, 1),
('M1YR above passbox', '', '', 156, 0, 1),
('M2 main corridor', '', '', 157, 0, 1),
('BMS room behind entrance door', '', '', 158, 0, 1),
('BMS service corridor entrance', '', '', 159, 0, 1),
('Nano electrical/AHU panel', '', '', 160, 0, 1),
('Nano2 lab near emergency exit door', '', '', 161, 0, 1),
('NanoYR lab above the passbox', '', '', 162, 0, 1),
('Nano lab above the passbox', '', '', 163, 0, 1),
('PPMS/spintronics/2D entrance lobby', '', '', 164, 0, 1),
('EC lab entrance door', '', '', 165, 0, 1),
('MBE Service Corridor', '', '', 166, 0, 1),
('Near 3rd floor Toilet', '', '', 167, 0, 1),
('Near 5rd floor Toilet', '', '', 168, 0, 1),
('outside nano-2 service corridor', '', '', 169, 0, 1),
('Outside MYR AHU room', '', '', 170, 0, 1),
('outside NB AHU room', '', '', 171, 0, 1),
('New Building', '', '', 172, 0, 1),
('AFM Room', '', '', 173, 0, 1),
('TESTING BY IT TEAM ON INTERNET insert worked', '1064', '1', 174, 1, 1),
('IT team test', '', '', 175, 0, 1),
('Test Run', '1064', '', 186, 0, 1),
('Testing by IT Team tausif 123', '2423,2249,2248', '265,2234', 176, 0, 1),
('IITBNF Office', '', '', 177, 0, 1),
('NanoE Conference Room', '', '', 178, 0, 1),
('NanoE Emergency Exit Door', '', '', 179, 0, 1),
('IITBNF GF Lab Entrance Annex', '', '', 180, 0, 1),
('IITBNF GF Lab Entrance Nano', '', '', 181, 0, 1),
('MicroE Office', '', '', 182, 0, 1),
('CEN Conference Room', '', '', 183, 0, 1),
('2nd Floor Annex Building Corridor', '', '', 184, 0, 1),
('AQM Labs Corridor', '', '', 185, 0, 1),
('ABC', '', '', 187, 0, 1),
('ABCTest', '', '', 188, 0, 1),
('Priya', '', '1', 189, 0, 1);

--
-- Indexes for dumped tables
--

--
-- Indexes for table `lab_incharge`
--
ALTER TABLE `lab_incharge`
  ADD PRIMARY KEY (`locationid`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `lab_incharge`
--
ALTER TABLE `lab_incharge`
  MODIFY `locationid` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=190;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
