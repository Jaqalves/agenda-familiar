import importlib.util
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

with tempfile.TemporaryDirectory() as isolated_home:
    with patch.object(Path, 'home', return_value=Path(isolated_home)):
        spec = importlib.util.spec_from_file_location('agenda', Path(__file__).resolve().parents[1] / 'agenda_familiar.py')
        agenda = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agenda)


def event(**changes):
    value = {
        'summary': 'Atividade fictícia',
        'description': 'Observação fictícia',
        'location': 'Local fictício',
        'iCalUID': 'evento-exemplo',
        'start': {'dateTime': '2030-05-06T08:00:00-03:00'},
        'end': {'dateTime': '2030-05-06T09:00:00-03:00'},
    }
    value.update(changes)
    return value


class AgendaRules(unittest.TestCase):
    def test_private_event_hides_details(self):
        record = agenda.event_record(event(visibility='private'), {'id': 'a'}, 'f')
        self.assertEqual(record['title'], 'Compromisso reservado')
        self.assertEqual((record['notes'], record['location']), ('', ''))

    def test_professional_event_is_generic(self):
        record = agenda.event_record(event(), {'id': 'a'}, 'p')
        self.assertEqual(record['title'], 'Compromisso profissional')
        self.assertFalse(record['physical'])
        self.assertEqual(record['notes'], '')

    def test_cancelled_or_declined_events_are_ignored(self):
        self.assertIsNone(agenda.event_record(event(status='cancelled'), {'id': 'a'}, 'f'))
        self.assertIsNone(agenda.event_record(event(attendees=[{'self': True, 'responseStatus': 'declined'}]), {'id': 'a'}, 'f'))

    def test_all_day_has_no_artificial_display_time(self):
        record = agenda.event_record(event(start={'date': '2030-05-06'}, end={'date': '2030-05-07'}), {'id': 'a'}, 'f')
        message = agenda.format_message([record], date(2030, 5, 6))
        self.assertIn('📌 Dia inteiro — Atividade fictícia', message)
        self.assertNotIn('00h00', message)

    def test_utc_is_converted_to_brasilia(self):
        self.assertEqual(agenda.moment({'dateTime': '2030-05-06T11:00:00Z'}).hour, 8)

    def test_unknown_calendar_blocks_collection(self):
        with patch.object(agenda, 'calendars', return_value=[{'id': 'desconhecido'}]):
            with self.assertRaises(RuntimeError):
                agenda.collect(MagicMock(), {'calendarios': {}}, date(2030, 5, 6))

    def test_duplicate_uses_more_restrictive_privacy(self):
        api = MagicMock()
        api.events.return_value.list.return_value.execute.side_effect = [
            {'items': [event()]}, {'items': [event(visibility='private')]}
        ]
        config = {'calendarios': {'a': {'modo': 'f'}, 'b': {'modo': 'f'}}}
        with patch.object(agenda, 'calendars', return_value=[{'id': 'a'}, {'id': 'b'}]):
            records = agenda.collect(api, config, date(2030, 5, 6))
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['title'], 'Compromisso reservado')
        self.assertEqual(records[0]['notes'], '')

    def test_empty_agenda_is_explicit(self):
        message = agenda.format_message([], date(2030, 5, 6))
        self.assertEqual(message.count('Não há compromissos registrados.'), 2)

    def test_draft_normalization_preserves_meaning(self):
        self.assertTrue(agenda.same_draft('☀️ Agenda\n08h00', '☀ Agenda 08h00'))
        self.assertFalse(agenda.same_draft('Agenda 08h00', 'Agenda 09h00'))


if __name__ == '__main__':
    unittest.main()
