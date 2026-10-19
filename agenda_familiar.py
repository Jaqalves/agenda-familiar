#!/usr/bin/env python3
"""Agenda familiar local. Prévia é o padrão; envio e agendamento são explícitos."""
import argparse
import fcntl
import html
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import datetime, timedelta, time
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path.home() / 'AgendaFamiliar'
TZ = ZoneInfo('America/Sao_Paulo')
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
LABEL = 'br.agendafamiliar.resumo'
DAYS = ['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira', 'sábado', 'domingo']


def save(path, value):
    tmp = path.with_suffix(path.suffix + '.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    tmp.chmod(0o600)
    tmp.replace(path)


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


# Preferências públicas de apresentação; credenciais ficam em arquivos separados.
PREFERENCES = read(ROOT / 'preferencias.json', {})
GROUP_NAME = PREFERENCES.get('grupo', 'Agenda Familiar')
GROUP_QUERY = PREFERENCES.get('busca_grupo', GROUP_NAME)
GREETING = PREFERENCES.get('saudacao', '☀️ *BOM DIA, FAMÍLIA!*')
if not isinstance(GROUP_NAME, str) or not GROUP_NAME.strip():
    raise RuntimeError('Configure um nome de grupo válido em preferencias.json.')
GROUP_KEY = 'grupo:' + hashlib.sha256(GROUP_NAME.encode()).hexdigest()[:20]
DESTINATIONS = [(GROUP_NAME, GROUP_KEY)]


def service():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds = Credentials.from_authorized_user_file(str(ROOT / 'token.json'), SCOPES)
    if not creds.valid:
        if not creds.refresh_token:
            raise RuntimeError('Google precisa de nova autorização. Execute: autorizar')
        creds.refresh(Request())
        save(ROOT / 'token.json', json.loads(creds.to_json()))
    return build('calendar', 'v3', credentials=creds, cache_discovery=False)


def calendars(api):
    result, token = [], None
    while True:
        page = api.calendarList().list(pageToken=token, maxResults=250).execute()
        result.extend(c for c in page.get('items', []) if not c.get('deleted') and not c.get('hidden'))
        token = page.get('nextPageToken')
        if not token:
            return result


def setup():
    api = service()
    config = read(ROOT / 'config.json', {'calendarios': {}})
    print('Escolha o tratamento de CADA calendário:')
    print('F = familiar: permite títulos, locais e descrições (exceto eventos privados).')
    print('P = profissional: mostra somente Compromisso profissional.')
    print('M = misto: oculta detalhes; só revela eventos com [familia] no título.')
    print('I = ignorar. Novos calendários não configurados bloquearão o envio.')
    for c in calendars(api):
        current = config['calendarios'].get(c['id'], {}).get('modo', 'm')
        while True:
            mode = input(f"\n{c.get('summary', c['id'])} [F/P/M/I; Enter={current.upper()}]: ").strip().lower() or current
            if mode in ('f', 'p', 'm', 'i'):
                break
        config['calendarios'][c['id']] = {'modo': mode, 'nome': c.get('summary', c['id'])}
    save(ROOT / 'config.json', config)
    print('\nConfiguração salva. Gere a prévia com: previa')


def clean(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', value or ''))).strip()


def moment(value, zone=TZ):
    if 'date' in value:
        return datetime.combine(datetime.fromisoformat(value['date']).date(), time.min, TZ)
    parsed = datetime.fromisoformat(value['dateTime'].replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo(value.get('timeZone', str(zone))))
    return parsed.astimezone(TZ)


def event_record(e, c, mode):
    if e.get('status') == 'cancelled':
        return None
    if any(a.get('self') and a.get('responseStatus') == 'declined' for a in e.get('attendees', [])):
        return None
    if e.get('eventType') == 'workingLocation':
        return None
    start, end = moment(e['start']), moment(e['end'])
    raw = clean(e.get('summary'))
    private = e.get('visibility') in ('private', 'confidential')
    show = not private and (mode == 'f' or (mode == 'm' and '[familia]' in raw.lower()))
    title = clean(re.sub(r'\[familia\]', '', raw, flags=re.I)) if show and raw else ('Compromisso profissional' if mode == 'p' else 'Compromisso reservado')
    location = clean(e.get('location')) if show else ''
    physical = bool(location and not re.search(r'https?://|meet\.|zoom|teams|online|virtual', location, re.I))
    return dict(start=start, end=end, all_day='date' in e['start'], title=title,
                notes=clean(e.get('description')) if show else '', location=location,
                physical=physical, busy=e.get('transparency') != 'transparent',
                uid=e.get('iCalUID'), raw=raw, calendar=c['id'], hidden=not show,
                person=c.get('summary', 'Agenda'))


def collect(api, config, today):
    start = datetime.combine(today, time.min, TZ)
    end = start + timedelta(days=2)
    events = []
    for c in calendars(api):
        choice = config['calendarios'].get(c['id'])
        if choice is None:
            raise RuntimeError('Há um calendário novo. Execute configurar antes de enviar.')
        mode = choice['modo']
        if mode == 'i':
            continue
        if c.get('accessRole') == 'freeBusyReader':
            data = api.freebusy().query(body={'timeMin': start.isoformat(), 'timeMax': end.isoformat(), 'timeZone': str(TZ), 'items': [{'id': c['id']}]}).execute()
            item = data.get('calendars', {}).get(c['id'])
            if item is None or item.get('errors'):
                raise RuntimeError('Falha ao consultar disponibilidade. Nenhum resumo parcial será enviado.')
            for b in item.get('busy', []):
                e = {'start': {'dateTime': b['start']}, 'end': {'dateTime': b['end']}}
                events.append(event_record(e, c, 'm'))
            continue
        token = None
        while True:
            data = api.events().list(calendarId=c['id'], timeMin=start.isoformat(), timeMax=end.isoformat(),
                                     singleEvents=True, showDeleted=False, orderBy='startTime',
                                     timeZone=str(TZ), maxResults=2500, pageToken=token).execute()
            for e in data.get('items', []):
                record = event_record(e, c, mode)
                if record:
                    events.append(record)
            token = data.get('nextPageToken')
            if not token:
                break
    # Mesmo UID/ocorrência; ou cópias com título e período idênticos em calendários distintos.
    unique = []
    for e in events:
        match = next((x for x in unique if x['calendar'] != e['calendar'] and x['start'] == e['start'] and x['end'] == e['end'] and
                      ((e['uid'] and e['uid'] == x['uid']) or (e['raw'] and e['raw'].casefold() == x['raw'].casefold()))), None)
        if match is None:
            unique.append(e)
        elif e['hidden']:
            # A cópia mais restritiva prevalece.
            match.update(title=e['title'], notes='', location='', physical=False, hidden=True)
    return sorted(unique, key=lambda e: e['start'])


def format_message(events, today):
    parts = [GREETING]
    warnings = []
    counts = []
    for offset in range(2):
        day = today + timedelta(days=offset)
        lo = datetime.combine(day, time.min, TZ)
        hi = lo + timedelta(days=1)
        rows = [e for e in events if e['start'] < hi and e['end'] > lo]
        counts.append(len(rows))
        heading = '📅 *AGENDA DE HOJE' if not offset else '📆 *AMANHÃ'
        parts.append(f"\n{heading} — {DAYS[day.weekday()].upper()}, {day:%d/%m/%Y}*")
        if not rows:
            parts.append('Não há compromissos registrados.')
        for e in rows:
            when = 'Dia inteiro' if e['all_day'] else (e['start'].strftime('%Hh%M') if e['start'] >= lo else 'Em andamento desde ' + e['start'].strftime('%d/%m %Hh%M'))
            parts.append(f"{'📌' if e['all_day'] else '🕒'} {when} — {e['title']}")
            if e['location']:
                parts.append('   Local: ' + e['location'])
            if e['notes']:
                note = e['notes'][:600] + ('… (descrição completa no calendário)' if len(e['notes']) > 600 else '')
                parts.append('   Obs.: ' + note)
            if e['physical']:
                warnings.append(f"{day:%d/%m}: possível deslocamento para {e['title']}; confira o local informado.")
        busy = [e for e in rows if not e['all_day'] and e['busy']]
        for i, a in enumerate(busy):
            for b in busy[i+1:]:
                if max(a['start'], b['start'], lo) < min(a['end'], b['end'], hi):
                    at = max(a['start'], b['start'], lo).strftime('%Hh%M')
                    warnings.append(f"{day:%d/%m} às {at}: sobreposição entre {a['title']} e {b['title']} (pode envolver pessoas diferentes).")
    if warnings:
        parts.extend(['\n⚠️ *PONTOS DE ATENÇÃO*', *dict.fromkeys(warnings)])
    today_rows = [e for e in events if e['start'].date() == today and not e['all_day']]
    periods = {'manhã': 0, 'tarde': 0, 'noite': 0}
    for e in today_rows:
        periods['manhã' if e['start'].hour < 12 else 'tarde' if e['start'].hour < 18 else 'noite'] += 1
    summary = f'{counts[0]} compromisso(s) hoje e {counts[1]} amanhã.'
    if today_rows:
        highest = max(periods.values())
        busiest = ', '.join(p for p, n in periods.items() if n == highest)
        summary += f' Mais inícios de compromissos: {busiest}.'
    parts.extend(['\n💡 *RESUMO DO DIA*', summary, '\nTenham um ótimo dia!', f'\nAgenda familiar • {today:%d/%m/%Y}'])
    message = '\n'.join(parts)
    if len(message) > 12000:
        raise RuntimeError('Resumo muito longo. Revise as descrições antes do envio.')
    return message


def mark(ledger, day, destination, state):
    ledger.setdefault(day, {})[destination] = {'estado': state, 'hora': datetime.now(TZ).isoformat()}
    save(ROOT / 'envios.json', ledger)


GROUP_HEADER_JS = r"""expected => {
    const header = document.querySelector('#main header');
    if (!header) return false;
    const normalize = value => value.normalize('NFC')
        .replace(/[\u200b\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\ufe0f]/g, '')
        .replace(/\s+/g, ' ').trim();
    const read = node => {
        if (node.nodeType === Node.TEXT_NODE) return node.textContent;
        if (node.nodeType !== Node.ELEMENT_NODE) return '';
        if (node.tagName === 'IMG') return node.getAttribute('alt') || '';
        return [...node.childNodes].map(read).join('');
    };
    return [...header.querySelectorAll('[title], [aria-label], span')].some(el =>
        [el.getAttribute('title') || '', el.getAttribute('aria-label') || '', read(el)]
            .some(value => normalize(value) === normalize(expected)));
}"""


def verify_group_header(page):
    handle = page.wait_for_function(GROUP_HEADER_JS, arg=GROUP_NAME, timeout=30000)
    handle.dispose()


def open_family_group(page):
    """Seleciona apenas o grupo exato autorizado; não usa conversas semelhantes."""
    page.goto('https://web.whatsapp.com/', timeout=120000)
    side = page.locator('#side')
    side.wait_for(state='visible', timeout=120000)
    exact_title = '[title=' + json.dumps(GROUP_NAME, ensure_ascii=False) + ']:visible'
    matches = side.locator(exact_title)
    if not matches.count():
        print('Grupo fora da lista visível; localizando a pesquisa do WhatsApp.', flush=True)
        search_selector = '[contenteditable="true"], input[type="search"], input[type="text"]'
        handle = page.wait_for_function(r"""selector => {
            const candidates = [...document.querySelectorAll(selector)].filter(el =>
                !el.closest('#main') && el.getClientRects().length &&
                getComputedStyle(el).visibility !== 'hidden');
            const named = candidates.filter(el => /pesquis|busc|procur|search/i.test(
                ['aria-label','title','placeholder','data-placeholder'].map(a => el.getAttribute(a) || '').join(' ')));
            const matches = named.length ? named : candidates;
            if (matches.length !== 1) return false;
            matches[0].setAttribute('data-agenda-search', 'true');
            return true;
        }""", arg=search_selector, timeout=30000)
        handle.dispose()
        search = page.locator('[data-agenda-search="true"]')
        # Sem o emoji na consulta, mas a seleção continua exigindo o título completo exato.
        search.fill(GROUP_QUERY)
        matches.first.wait_for(state='visible', timeout=30000)
    if matches.count() != 1:
        raise RuntimeError('Mais de uma conversa com o nome exato do grupo. Nenhuma foi selecionada.')
    print('Grupo com título exato localizado; abrindo conversa.', flush=True)
    matches.click()
    print('Conversa selecionada; conferindo o nome visível no cabeçalho.', flush=True)
    header = page.locator('#main header')
    verify_group_header(page)
    print('Título do grupo conferido; abrindo Dados do grupo.', flush=True)
    header.click()
    try:
        page.get_by_text(re.compile(r'^(Dados do grupo|Group info)$', re.I)).first.wait_for(state='visible', timeout=15000)
    finally:
        page.keyboard.press('Escape')
    # Verifica novamente depois de fechar o painel, imediatamente antes de usar o editor.
    verify_group_header(page)


def send_button(page):
    footer = page.locator('#main footer')
    # Prioriza o nome acessível do botão, independente do nome interno do ícone.
    button = footer.get_by_role('button', name=re.compile(r'^(Enviar|Send)(?:\s+mensagem|\s+message)?$', re.I))
    if button.count() == 1 and button.is_visible():
        return button
    icons = footer.locator('[data-icon="send"], [data-icon="wds-ic-send-filled"]')
    if icons.count() == 1 and icons.is_visible():
        return icons
    raise RuntimeError('Botão Enviar não identificado com segurança. O rascunho foi preservado.')


def same_draft(actual, expected):
    def normalized(text):
        text = unicodedata.normalize('NFC', text)
        text = re.sub(r'[\u200b\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\ufe0f]', '', text)
        return re.sub(r'\s+', ' ', text).strip()
    return normalized(actual) == normalized(expected)


def read_draft(editor):
    # WhatsApp pode converter emojis em imagens ao restaurar um rascunho.
    # Lê texto e alt das imagens, preservando o conteúdo sem alterar a página.
    return editor.evaluate('''element => {
        function read(node) {
            if (node.nodeType === Node.TEXT_NODE) return node.textContent;
            if (node.nodeType !== Node.ELEMENT_NODE) return '';
            if (node.tagName === 'IMG') return node.getAttribute('alt') || '';
            if (node.tagName === 'BR') return '\\n';
            const text = Array.from(node.childNodes).map(read).join('');
            return ['DIV', 'P', 'LI'].includes(node.tagName) ? text + '\\n' : text;
        }
        return read(element);
    }''')


AGENDA_PROBE_JS = r"""({marker}) => {
    const main = document.querySelector('#main');
    const result = {present: false, confirmed: false, status: null, icons: [], structure: []};
    if (!main) return result;
    const normalize = text => text.normalize('NFC')
        .replace(/[\u200b\u200e\u200f\u202a-\u202e\u2066-\u2069\ufeff\ufe0f]/g, '')
        .replace(/\s+/g, ' ').trim();
    const expected = normalize(marker);
    const oldChecks = new Set(['msg-check', 'msg-dblcheck', 'msg-dblcheck-ack']);
    const svgChecks = new Set(['wds-ic-read', 'wds-ic-sent', 'wds-ic-delivered',
        'wds-ic-checkmark', 'wds-ic-checkmark-double', 'wds-ic-msg-check', 'wds-ic-msg-dblcheck']);
    for (const text of main.querySelectorAll('.selectable-text')) {
        if (text.closest('footer') || !normalize(text.innerText).includes(expected)) continue;
        result.present = true;
        const wrapper = text.closest('div.copyable-text');
        let el = wrapper ? wrapper.parentElement : text.parentElement;
        for (let depth = 0; el && el !== main && depth < 12; depth++, el = el.parentElement) {
            const diagnosticTitles = [...el.querySelectorAll('svg > title')]
                .map(node => node.textContent.trim()).filter(value => /^[a-z0-9-]{1,64}$/.test(value));
            result.structure.push({depth, textBlocks: el.querySelectorAll('div.copyable-text').length,
                titles: diagnosticTitles});
            // Nunca pega a confirmação de outra mensagem ou de um grupo de mensagens.
            if (wrapper) {
                // Blocos aninhados pertencem à mesma mensagem. Só blocos independentes
                // indicam que chegamos ao contêiner de várias mensagens.
                const wrappers = [...(el.matches('div.copyable-text') ? [el] : []),
                    ...el.querySelectorAll('div.copyable-text')];
                const roots = wrappers.filter(node => !wrappers.some(other =>
                    other !== node && other.contains(node)));
                if (roots.length !== 1 || !roots[0].contains(text)) break;
            } else if (el.querySelectorAll('.selectable-text').length !== 1) break;
            const icons = [...el.querySelectorAll('[data-icon]')]
                .map(node => node.getAttribute('data-icon'));
            const titles = [...el.querySelectorAll('svg > title')]
                .map(node => node.textContent.trim());
            const status = icons.find(icon => oldChecks.has(icon)) ||
                titles.find(title => svgChecks.has(title));
            result.icons = [...new Set([...result.icons, ...icons, ...titles])]
                .filter(value => /^[a-z0-9-]{1,64}$/.test(value));
            if (status) return {...result, confirmed: true, status};
        }
    }
    return result;
}"""


def agenda_probe(page, marker):
    return page.evaluate(AGENDA_PROBE_JS, {'marker': marker})


def wait_agenda_confirmation(page, marker, timeout=45000):
    predicate = 'arg => (' + AGENDA_PROBE_JS + ')(arg).confirmed'
    handle = page.wait_for_function(predicate, arg={'marker': marker}, timeout=timeout)
    handle.dispose()


def find_agenda_history(page, marker):
    """Percorre apenas a interface da conversa; nunca preenche ou envia texto."""
    page.locator('#main .selectable-text').first.wait_for(state='attached', timeout=30000)
    probe = agenda_probe(page, marker)
    if probe['present']:
        return probe
    for _ in range(30):
        # O WhatsApp só mantém um trecho do histórico no DOM. Rolar carrega o anterior.
        before = page.locator('#main').evaluate(r"""main => {
            const candidates = [...main.querySelectorAll('*')].filter(el =>
                el.clientHeight > 100 && el.scrollHeight > el.clientHeight + 20 &&
                el.querySelector('.selectable-text') &&
                /auto|scroll/.test(getComputedStyle(el).overflowY));
            const el = candidates.sort((a,b) => a.clientHeight-b.clientHeight)[0];
            if (!el) return null;
            const first = () => main.querySelector('.selectable-text')?.textContent.slice(0,160) || '';
            const before = {first: first(), height: el.scrollHeight, top: el.scrollTop};
            el.setAttribute('data-agenda-history-scroll', 'true');
            el.scrollTop = Math.max(0, el.scrollTop - el.clientHeight * 0.85);
            el.dispatchEvent(new Event('scroll', {bubbles: true}));
            return before;
        }""")
        if before is None:
            break
        try:
            handle = page.wait_for_function(r"""before => {
                const main = document.querySelector('#main');
                const el = main?.querySelector('[data-agenda-history-scroll]');
                return !el || el.scrollHeight !== before.height ||
                    (main.querySelector('.selectable-text')?.textContent.slice(0,160) || '') !== before.first;
            }""", arg=before, timeout=1800)
            handle.dispose()
        except Exception as exc:
            if type(exc).__name__ != 'TimeoutError':
                raise
        probe = agenda_probe(page, marker)
        if probe['present']:
            return probe
        if before['top'] == 0:
            break
    return agenda_probe(page, marker)


def send(message, today, recover=False, verify_only=False):
    from playwright.sync_api import sync_playwright
    ledger = read(ROOT / 'envios.json', {})
    day = today.isoformat()
    marker = f'Agenda familiar • {today:%d/%m/%Y}'
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(str(ROOT / 'perfil-whatsapp'), channel='chrome', headless=False, no_viewport=True)
        page = browser.pages[0] if browser.pages else browser.new_page()
        try:
            for name, destination in DESTINATIONS:
                state = ledger.get(day, {}).get(destination, {}).get('estado')
                pending = state == 'incerto_verificar_whatsapp'
                if state and not (recover and pending):
                    print(f'{name}: {state}; não reenviado.')
                    continue
                stage = 'abrir conversa'
                try:
                    stage = 'localizar e verificar o grupo exato'
                    open_family_group(page)
                    stage = 'localizar campo de mensagem'
                    editor = page.locator('#main footer [contenteditable="true"][role="textbox"]')
                    editor.wait_for(state='visible', timeout=120000)
                    print(f'{name}: nome exato e dados do grupo conferidos.', flush=True)
                    stage = 'verificar histórico e rascunho'
                    old = find_agenda_history(page, marker) if recover else agenda_probe(page, marker)
                    if old['present']:
                        stage = 'conferir confirmação da mensagem no histórico'
                        try:
                            wait_agenda_confirmation(page, marker, timeout=15000)
                        except Exception:
                            diagnostic = agenda_probe(page, marker)
                            details = ', '.join(diagnostic['icons']) or 'nenhum'
                            print(f'{name}: identificadores de confirmação encontrados: {details}.')
                            print('Estrutura técnica (sem texto das conversas): ' + json.dumps(diagnostic['structure'], ensure_ascii=False))
                            raise
                        mark(ledger, day, destination, 'confirmado')
                        print(f'{name}: envio confirmado no histórico; não reenviado.')
                        continue
                    if verify_only:
                        raise RuntimeError('Resumo não localizado no trecho de histórico carregado. Conferência encerrada sem envio.')
                    draft = read_draft(editor)
                    if pending and recover:
                        if not draft.strip():
                            raise RuntimeError('RECUPERAÇÃO: campo vazio. O WhatsApp não restaurou o rascunho; nenhum novo envio será tentado sem conferir o histórico.')
                        if not same_draft(draft, message):
                            raise RuntimeError(f'RECUPERAÇÃO: conteúdo diferente mesmo após normalizar emojis e espaços. Rascunho: {len(draft)} caracteres; resumo: {len(message)}. Não foi alterado nem enviado.')
                        print(f'{name}: rascunho intacto conferido; recuperando a tentativa.', flush=True)
                    elif draft.strip():
                        raise RuntimeError('Há um rascunho na conversa; não foi alterado.')
                    else:
                        stage = 'preencher mensagem'
                        editor.fill(message)
                    if not same_draft(read_draft(editor), message):
                        raise RuntimeError('O texto no campo não coincide com o resumo.')
                    stage = 'localizar botão Enviar'
                    button = send_button(page)
                    # Antes de clicar: qualquer interrupção posterior exige conferência manual.
                    mark(ledger, day, destination, 'incerto_verificar_whatsapp')
                    stage = 'clicar em Enviar'
                    button.click(timeout=10000)
                    stage = 'confirmar marca de envio'
                    wait_agenda_confirmation(page, marker)
                    mark(ledger, day, destination, 'confirmado')
                    print(f'{name}: envio confirmado pela marca do WhatsApp (não implica leitura).')
                except Exception as exc:
                    # Não imprime conversas, tokens ou URLs de autorização no log.
                    print(f'{name}: parou em {stage} ({type(exc).__name__}). Confira a conversa; não há repetição automática após clique.')
                    if isinstance(exc, RuntimeError):
                        print(str(exc))
        finally:
            browser.close()
    complete = all(ledger.get(day, {}).get(destination, {}).get('estado') == 'confirmado' for _, destination in DESTINATIONS)
    if complete:
        save(ROOT / 'teste_ok.json', {'data': day, 'destinatarios': [key for _, key in DESTINATIONS]})
    return complete


def authorize():
    from google_auth_oauthlib.flow import InstalledAppFlow
    source = Path.home() / 'Downloads' / 'credentials.json'
    flow = InstalledAppFlow.from_client_secrets_file(str(source), SCOPES)
    creds = flow.run_local_server(port=0, prompt='consent')
    save(ROOT / 'token.json', json.loads(creds.to_json()))
    print('Autorização renovada.')


def schedule(enable):
    if sys.platform != 'darwin':
        raise RuntimeError('Agendamento disponível apenas no macOS.')
    agent = Path.home() / 'Library' / 'LaunchAgents' / (LABEL + '.plist')
    target = f'gui/{os.getuid()}'
    if not enable:
        subprocess.run(['launchctl', 'bootout', target + '/' + LABEL], capture_output=True)
        agent.unlink(missing_ok=True)
        print('Agendamento removido.')
        return
    tested = read(ROOT / 'teste_ok.json', {})
    if tested.get('destinatarios') != [key for _, key in DESTINATIONS]:
        raise RuntimeError(f'Antes de ativar, execute enviar e confirme o envio ao grupo {GROUP_NAME}.')
    installed = ROOT / 'agenda_familiar.py'
    if Path(__file__).resolve() != installed.resolve():
        shutil.copy2(__file__, installed)
    tomorrow = datetime.now(TZ).date() + timedelta(days=1)
    save(ROOT / 'agendamento.json', {'inicio': tomorrow.isoformat()})
    agent.parent.mkdir(parents=True, exist_ok=True)
    payload = {'Label': LABEL, 'ProgramArguments': [str(ROOT / '.venv/bin/python'), str(installed), 'automatico'],
               'StartInterval': 60, 'RunAtLoad': True, 'WorkingDirectory': str(ROOT),
               'StandardOutPath': str(ROOT / 'rotina.log'), 'StandardErrorPath': str(ROOT / 'erros.log')}
    agent.write_bytes(plistlib.dumps(payload))
    agent.chmod(0o600)
    subprocess.run(['launchctl', 'bootout', target + '/' + LABEL], capture_output=True)
    subprocess.run(['launchctl', 'bootstrap', target, str(agent)], check=True)
    subprocess.run(['launchctl', 'print', target + '/' + LABEL], check=True, stdout=subprocess.DEVNULL)
    print(f'Agendamento registrado a partir de {tomorrow:%d/%m/%Y}, às 07h10 de Brasília, todos os dias.')
    print('Mac ligado, acordado e usuário conectado são necessários. Sem recuperação tardia após 07h14.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('acao', choices=['configurar', 'previa', 'enviar', 'recuperar', 'conferir', 'ativar', 'desativar', 'automatico', 'autorizar', 'status'], nargs='?', default='previa')
    args = parser.parse_args()
    os.umask(0o077)
    ROOT.mkdir(exist_ok=True)
    with (ROOT / 'rotina.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        if args.acao == 'configurar':
            setup()
            return 0
        if args.acao == 'autorizar':
            authorize()
            return 0
        if args.acao in ('ativar', 'desativar'):
            schedule(args.acao == 'ativar')
            return 0
        if args.acao == 'status':
            print(json.dumps(read(ROOT / 'envios.json', {}), indent=2, ensure_ascii=False))
            return 0
        now = datetime.now(TZ)
        today = now.date()
        if args.acao == 'conferir':
            if not send('', today, recover=True, verify_only=True):
                raise RuntimeError('Conferência incompleta. Nenhuma mensagem foi enviada.')
            print('Envio ao grupo confirmado. O agendamento pode ser ativado.')
            return 0
        if args.acao == 'automatico':
            scheduling = read(ROOT / 'agendamento.json', {})
            if not scheduling or today.isoformat() < scheduling['inicio'] or now.hour != 7 or not 10 <= now.minute <= 14:
                return 0
            attempts = read(ROOT / 'tentativas.json', {})
            if today.isoformat() in attempts:
                return 0
            attempts[today.isoformat()] = now.isoformat()
            save(ROOT / 'tentativas.json', attempts)
        config = read(ROOT / 'config.json')
        if not config:
            raise RuntimeError('Execute configurar primeiro.')
        events = collect(service(), config, today)
        message = format_message(events, today)
        if args.acao == 'previa':
            print(message)
            (ROOT / 'previa.txt').write_text(message)
            print('\nPRÉVIA: nenhuma mensagem enviada.')
            return 0
        ok = send(message, today, recover=args.acao == 'recuperar')
        if not ok:
            raise RuntimeError('Nem todos os envios foram confirmados. Use status e confira o WhatsApp.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        print(f'FALHA: {type(exc).__name__}. A execução não foi concluída.', file=sys.stderr)
        if isinstance(exc, RuntimeError):
            print(str(exc), file=sys.stderr)
        if sys.platform == 'darwin' and 'automatico' in sys.argv:
            subprocess.run(['osascript', '-e', 'display notification "O resumo não foi totalmente enviado. Confira AgendaFamiliar/erros.log e o WhatsApp." with title "Agenda Familiar: falha"'], capture_output=True)
        sys.exit(1)
