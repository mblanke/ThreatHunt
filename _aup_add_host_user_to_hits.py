from pathlib import Path
p=Path(r'd:/Projects/Dev/ThreatHunt/backend/app/services/scanner.py')
t=p.read_text(encoding='utf-8')

# 1) Extend ScanHit dataclass
old='''@dataclass
class ScanHit:
    theme_name: str
    theme_color: str
    keyword: str
    source_type: str       # dataset_row | hunt | annotation | message
    source_id: str | int
    field: str
    matched_value: str
    row_index: int | None = None
    dataset_name: str | None = None
'''
new='''@dataclass
class ScanHit:
    theme_name: str
    theme_color: str
    keyword: str
    source_type: str       # dataset_row | hunt | annotation | message
    source_id: str | int
    field: str
    matched_value: str
    row_index: int | None = None
    dataset_name: str | None = None
    hostname: str | None = None
    username: str | None = None
'''
if old not in t:
    raise SystemExit('ScanHit dataclass block not found')
t=t.replace(old,new)

# 2) Add helper to infer hostname/user from a row
insert_after='''BATCH_SIZE = 200


@dataclass
class ScanHit:
'''
helper='''BATCH_SIZE = 200


def _infer_hostname_and_user(data: dict) -> tuple[str | None, str | None]:
    """Best-effort extraction of hostname and user from a dataset row."""
    if not data:
        return None, None

    host_keys = (
        'hostname', 'host_name', 'host', 'computer_name', 'computer',
        'fqdn', 'client_id', 'agent_id', 'endpoint_id',
    )
    user_keys = (
        'username', 'user_name', 'user', 'account_name',
        'logged_in_user', 'samaccountname', 'sam_account_name',
    )

    def pick(keys):
        for k in keys:
            for actual_key, v in data.items():
                if actual_key.lower() == k and v not in (None, ''):
                    return str(v)
        return None

    return pick(host_keys), pick(user_keys)


@dataclass
class ScanHit:
'''
if insert_after in t and '_infer_hostname_and_user' not in t:
    t=t.replace(insert_after,helper)

# 3) Extend _match_text signature and ScanHit construction
old_sig='''    def _match_text(
        self,
        text: str,
        patterns: dict,
        source_type: str,
        source_id: str | int,
        field_name: str,
        hits: list[ScanHit],
        row_index: int | None = None,
        dataset_name: str | None = None,
    ) -> None:
'''
new_sig='''    def _match_text(
        self,
        text: str,
        patterns: dict,
        source_type: str,
        source_id: str | int,
        field_name: str,
        hits: list[ScanHit],
        row_index: int | None = None,
        dataset_name: str | None = None,
        hostname: str | None = None,
        username: str | None = None,
    ) -> None:
'''
if old_sig not in t:
    raise SystemExit('_match_text signature not found')
t=t.replace(old_sig,new_sig)

old_hit='''                    hits.append(ScanHit(
                        theme_name=theme_name,
                        theme_color=theme_color,
                        keyword=kw_value,
                        source_type=source_type,
                        source_id=source_id,
                        field=field_name,
                        matched_value=matched_preview,
                        row_index=row_index,
                        dataset_name=dataset_name,
                    ))
'''
new_hit='''                    hits.append(ScanHit(
                        theme_name=theme_name,
                        theme_color=theme_color,
                        keyword=kw_value,
                        source_type=source_type,
                        source_id=source_id,
                        field=field_name,
                        matched_value=matched_preview,
                        row_index=row_index,
                        dataset_name=dataset_name,
                        hostname=hostname,
                        username=username,
                    ))
'''
if old_hit not in t:
    raise SystemExit('ScanHit append block not found')
t=t.replace(old_hit,new_hit)

# 4) Pass inferred hostname/username in dataset scan path
old_call='''                for row in rows:
                    result.rows_scanned += 1
                    data = row.data or {}
                    for col_name, cell_value in data.items():
                        if cell_value is None:
                            continue
                        text = str(cell_value)
                        self._match_text(
                            text,
                            patterns,
                            "dataset_row",
                            row.id,
                            col_name,
                            result.hits,
                            row_index=row.row_index,
                            dataset_name=ds_name,
                        )
'''
new_call='''                for row in rows:
                    result.rows_scanned += 1
                    data = row.data or {}
                    hostname, username = _infer_hostname_and_user(data)
                    for col_name, cell_value in data.items():
                        if cell_value is None:
                            continue
                        text = str(cell_value)
                        self._match_text(
                            text,
                            patterns,
                            "dataset_row",
                            row.id,
                            col_name,
                            result.hits,
                            row_index=row.row_index,
                            dataset_name=ds_name,
                            hostname=hostname,
                            username=username,
                        )
'''
if old_call not in t:
    raise SystemExit('dataset _match_text call block not found')
t=t.replace(old_call,new_call)

p.write_text(t,encoding='utf-8')
print('updated scanner hits with hostname+username context')
