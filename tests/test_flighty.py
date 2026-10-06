"""Integration tests run the real CLI against synthetic Flighty databases."""
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/flighty/scripts/flighty.py'
NOW = '2026-10-06T12:00:00Z'


def fixture(path):
    conn = sqlite3.connect(path)
    conn.executescript('''
    CREATE TABLE Airport(id TEXT PRIMARY KEY, iata TEXT, icao TEXT, name TEXT, city TEXT,
      country TEXT, timeZoneIdentifier TEXT, relevance INTEGER, deleted INTEGER);
    CREATE TABLE Airline(id TEXT PRIMARY KEY, iata TEXT, icao TEXT, name TEXT, alliance TEXT,
      relevance INTEGER, deleted INTEGER);
    CREATE TABLE Flight(id TEXT PRIMARY KEY, number TEXT, departureAirportId TEXT,
      scheduledArrivalAirportId TEXT, actualArrivalAirportId TEXT, airlineId TEXT,
      isCancelled INTEGER, hasOfficialData TEXT, distance REAL, lastKnownDepartureDate INTEGER,
      lastKnownArrivalDate INTEGER, departureScheduleGateOriginal INTEGER,
      arrivalScheduleGateOriginal INTEGER, departureScheduleGateEstimated INTEGER,
      arrivalScheduleGateEstimated INTEGER, departureScheduleGateActual INTEGER,
      arrivalScheduleGateActual INTEGER, departureGate TEXT, arrivalWeatherConditionName TEXT,
      delayForecastObservations INTEGER, delayForecastDelayMean REAL,
      delayForecastOntimeCount INTEGER, delayForecastEarlyCount INTEGER,
      created INTEGER, lastUpdated INTEGER, deleted INTEGER);
    CREATE TABLE UserFlight(userId TEXT, flightId TEXT REFERENCES Flight(id), isArchived INTEGER,
      isRandom INTEGER, isProUpgrade INTEGER, isMyFlight INTEGER, importSource TEXT,
      created INTEGER, lastUpdated INTEGER, deleted INTEGER, PRIMARY KEY(userId,flightId));
    CREATE TABLE Ticket(userId TEXT, flightId TEXT REFERENCES Flight(id), seatNumber TEXT,
      seatPosition TEXT, cabinClass TEXT, pnr TEXT, lastUpdated INTEGER, deleted INTEGER);
    CREATE TABLE Profile(userId TEXT, fullName TEXT, firstName TEXT, deleted INTEGER);
    CREATE TABLE ConnectedFriendRelationship(senderUserId TEXT,receiverUserId TEXT,deleted INTEGER);
    CREATE TABLE Connection(id TEXT, arrivingFlightId TEXT, departingFlightId TEXT,
      waitingAirportId TEXT, mctMinutes INTEGER, deleted INTEGER);
    INSERT INTO Airport VALUES('ewr','EWR','KEWR','Newark','Newark','US','America/New_York',10,NULL);
    INSERT INTO Airport VALUES('zrh','ZRH','LSZH','Zürich Airport','Zürich','CH','Europe/Zurich',10,NULL);
    INSERT INTO Airline VALUES('ua','UA','UAL','United Airlines','Star Alliance',10,NULL);
    INSERT INTO Profile VALUES('friend','Felix Example','Felix',NULL);
    INSERT INTO ConnectedFriendRelationship VALUES('owner','friend',NULL);
    INSERT INTO ConnectedFriendRelationship VALUES('owner','other',NULL);
    ''')
    departures = [1791201600, 1791374400, 1791374400, 1791460800]
    for index, departure in enumerate(departures):
        conn.execute('''INSERT INTO Flight(id,number,departureAirportId,scheduledArrivalAirportId,
          airlineId,isCancelled,distance,departureScheduleGateOriginal,arrivalScheduleGateOriginal,
          departureScheduleGateEstimated,delayForecastObservations,delayForecastOntimeCount,
          delayForecastEarlyCount,arrivalWeatherConditionName)
          VALUES(?, '194', 'ewr', 'zrh', 'ua', 0, 1000, ?, ?, ?, 10, 8, 1, 'sunny')''',
                     (f'f{index}', departure, departure + 3600, departure + 1200))
        conn.execute('INSERT INTO UserFlight(userId,flightId,isArchived) VALUES(?,?,0)',
                     ('friend' if index == 2 else 'owner', f'f{index}'))
    conn.execute("INSERT INTO Ticket(userId,flightId,seatNumber,pnr) VALUES('owner','f1','12A','OWN123')")
    conn.execute("INSERT INTO Ticket(userId,flightId,seatNumber,pnr) VALUES('friend','f2','13A','FRI123')")
    conn.execute("INSERT INTO Connection VALUES('c1','f1','f3','zrh',1500,NULL)")
    conn.execute("INSERT INTO Connection VALUES('c2','f2','f3','zrh',60,NULL)")
    conn.commit()
    conn.close()


class CLI(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / 'test ? flights.db'
        fixture(self.db)

    def run_cli(self, *args, success=True, env=None, db=None):
        proc = subprocess.run([sys.executable, str(SCRIPT), '--db', str(db or self.db), '--now', NOW, *args],
                              text=True, capture_output=True, env=env, timeout=10)
        self.assertEqual(proc.returncode, 0 if success else 1, proc.stderr)
        if success:
            self.assertEqual(proc.stderr, '')
            payload = json.loads(proc.stdout)
            self.assertTrue(payload['ok'])
            return payload['data']
        self.assertEqual(proc.stdout, '')
        payload = json.loads(proc.stderr)
        self.assertFalse(payload['ok'])
        return payload['error']

    def sql(self, statement):
        with sqlite3.connect(self.db) as conn:
            conn.execute(statement)

    def test_owner_friend_and_ticket_isolation(self):
        rows = self.run_cli('list', '--include-archived')
        self.assertEqual([r['id'] for r in rows], ['f0', 'f1', 'f3'])
        self.assertEqual(rows[1]['pnr'], 'OWN123')
        friends = self.run_cli('friends', '--friend', 'Felix')
        self.assertEqual([r['id'] for r in friends], ['f2'])
        self.assertEqual(friends[0]['pnr'], 'FRI123')
        self.assertEqual(self.run_cli('get', '--flight', 'UA194')['id'], 'f3')
        self.assertEqual(self.run_cli('get', '--flight', 'UA 194', '--date', '2026-10-07')['id'], 'f1')

    def test_filters_pagination_and_repeatability(self):
        first = self.run_cli('list', '--upcoming', '--limit', '1')
        self.assertEqual([r['id'] for r in first], ['f1'])
        self.assertEqual(first, self.run_cli('list', '--upcoming', '--limit', '1'))
        self.assertEqual(self.run_cli('list', '--upcoming', '--offset', '1')[0]['id'], 'f3')
        self.assertEqual(len(self.run_cli('search', '--arrival-airport', 'Zurich')), 3)
        self.assertEqual(self.run_cli('search', '--airline', "' OR 1=1 --"), [])
        self.assertEqual(self.run_cli('search', '--after', '2027-01-01'), [])
        self.run_cli('search', '--after', '2027-01-01', '--before', '2026-01-01', success=False)

    def test_archive_and_deleted(self):
        self.sql("UPDATE UserFlight SET isArchived=1 WHERE flightId='f0'")
        self.assertIn('f0', [r['id'] for r in self.run_cli('list')])  # automatic archive heuristic
        self.sql("UPDATE UserFlight SET isArchived=1 WHERE flightId='f1'")
        self.sql("UPDATE Flight SET deleted=1 WHERE id='f3'")
        self.assertEqual(len(self.run_cli('list', '--include-archived')), 2)

    def test_status_forecast_stats_connections(self):
        self.assertEqual(self.run_cli('status', '--id', 'f1')['departure_delay_minutes'], 20)
        self.assertEqual(self.run_cli('status', '--id', 'f1')['status'], 'delayed')
        forecast = self.run_cli('forecast', '--id', 'f1')
        self.assertEqual(forecast['ontime_pct'], 80)
        self.assertIsNone(forecast['late_15_pct'])
        stats = self.run_cli('stats', '--year', '2026')
        self.assertEqual(stats['total_flights'], 3)
        self.assertEqual(stats['total_distance_km'], 3000)
        self.assertEqual(stats['unique_countries'], 2)
        self.assertEqual(len(self.run_cli('connections')), 1)
        self.assertTrue(self.run_cli('connections')[0]['below_minimum'])
        self.sql("UPDATE Flight SET isCancelled=1 WHERE id='f1'")
        self.assertEqual(self.run_cli('status', '--id', 'f1')['status'], 'cancelled')

    def test_catalog_and_weather_schema(self):
        self.assertEqual(self.run_cli('airports', 'Zurich')[0]['iata'], 'ZRH')
        self.assertEqual(self.run_cli('airlines', 'Star')[0]['iata'], 'UA')
        self.assertEqual(self.run_cli('get', '--id', 'f1')['arrivalWeatherConditionName'], 'sunny')
        self.sql('ALTER TABLE Flight RENAME COLUMN arrivalWeatherConditionName TO arrivalWeatherCondition')
        self.assertEqual(self.run_cli('get', '--id', 'f1')['arrivalWeatherCondition'], 'sunny')

    def test_opaque_binary_flight_fields(self):
        self.sql('ALTER TABLE Flight ADD COLUMN appState BLOB')
        self.sql("UPDATE Flight SET appState=X'00FF' WHERE id='f1'")
        rows = self.run_cli('list', '--upcoming')
        self.assertEqual(rows[0]['id'], 'f1')
        self.assertNotIn('appState', rows[0])
        self.assertNotIn('appState', self.run_cli('get', '--id', 'f1'))
        self.assertEqual(self.run_cli('status', '--id', 'f1')['status'], 'delayed')

    def test_timezone_independence(self):
        args = ['search', '--after', '2026-10-07']
        utc = self.run_cli(*args, env=dict(os.environ, TZ='UTC'))
        west = self.run_cli(*args, env=dict(os.environ, TZ='America/Los_Angeles'))
        self.assertEqual(utc, west)

    def test_diagnostics_and_invalid_input(self):
        self.assertIn('owner', self.run_cli('doctor')['users'])
        self.run_cli('list', '--limit', '-1', success=False)
        self.run_cli('list', '--upcoming', '--past', success=False)
        self.run_cli('get', '--flight', 'invalid', success=False)
        self.run_cli('get', '--id', 'missing', success=False)
        self.run_cli('stats', '--year', '10000', success=False)
        missing = Path(self.temp.name) / 'missing.db'
        self.run_cli('doctor', success=False, db=missing)
        self.assertFalse(missing.exists())
        self.sql('DELETE FROM ConnectedFriendRelationship')
        self.sql("DELETE FROM UserFlight WHERE flightId IN ('f0','f3')")
        self.assertIn('ambiguous', self.run_cli('list', success=False))
        self.assertEqual(len(self.run_cli('--user-id', 'owner', 'list')), 1)

    def add_args(self):
        return ['add', '--flight', 'UA999', '--departure-airport', 'EWR', '--arrival-airport', 'ZRH',
                '--departure', '2026-12-01T20:00:00-05:00', '--arrival', '2026-12-02T10:00:00+01:00',
                '--seat', '12A', '--booking-reference', 'TEST']

    def test_preview_write_backup_and_idempotency(self):
        before = self.db.read_bytes()
        preview = self.run_cli(*self.add_args())
        self.assertFalse(preview['written'])
        self.assertEqual(before, self.db.read_bytes())
        backup = Path(self.temp.name) / 'backup.db'
        written = self.run_cli(*self.add_args(), '--write', '--backup', str(backup))
        self.assertTrue(written['written'])
        self.assertEqual(preview['flight_id'], written['flight_id'])
        with sqlite3.connect(backup) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM Flight').fetchone()[0], 4)
        new = self.run_cli('get', '--id', written['flight_id'])
        self.assertEqual(new['pnr'], 'TEST')
        self.assertEqual(new['departureScheduleGateOriginal'], '2026-12-02T01:00:00+00:00')
        self.assertEqual(self.run_cli(*self.add_args(), '--write', '--backup', str(backup))['action'], 'already_exists')
        self.assertEqual(len(self.run_cli('list')), 4)

    def test_write_constraints_rollback_and_backup_protection(self):
        self.run_cli(*self.add_args(), '--write', success=False)
        backup = Path(self.temp.name) / 'backup.db'
        backup.write_text('do not overwrite')
        self.run_cli(*self.add_args(), '--write', '--backup', str(backup), success=False)
        self.assertEqual(backup.read_text(), 'do not overwrite')
        self.sql("CREATE TRIGGER reject_ticket BEFORE INSERT ON Ticket BEGIN SELECT RAISE(ABORT,'test failure'); END")
        self.run_cli(*self.add_args(), '--write', '--backup', str(Path(self.temp.name) / 'safe.db'), success=False)
        self.assertEqual(len(self.run_cli('list')), 3)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM Flight').fetchone()[0], 4)
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM UserFlight').fetchone()[0], 4)

    def test_creation_validation(self):
        args = self.add_args()
        args[args.index('--arrival') + 1] = '2026-11-01T10:00:00+01:00'
        self.run_cli(*args, success=False)
        args = self.add_args()
        args[args.index('--departure') + 1] = '2026-12-01T20:00:00'
        self.run_cli(*args, success=False)
        self.sql('ALTER TABLE Flight DROP COLUMN hasOfficialData')
        self.run_cli(*self.add_args(), success=False)


if __name__ == '__main__':
    unittest.main()
