#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
EOP -> MIDI
Conversor de partituras Everyone Piano (.EOP) para Standard MIDI.

Uso:
    - Arraste um ou mais arquivos .EOP sobre este arquivo .py
    - ou execute: python eop_to_midi.py musica.eop
    - múltiplos arquivos também são aceitos

Não requer bibliotecas externas.
Suporta EOP 2.00, 2.01 e 3.01.
Em EOP 2.00, a informação de mão esquerda/direita é preservada:
    MIDI Track 1 = Mão Esquerda
    MIDI Track 2 = Mão Direita

Para EOP 2.01/3.01, o formato de mapeamento não carrega uma
identificação esquerda/direita equivalente; nesses arquivos as notas
são colocadas em uma única pista Piano.
"""

import sys
import struct
import math
import traceback
from pathlib import Path


XOR_MASK = bytes([
    0x71, 0x72, 0x73, 0x74, 0x72, 0x73, 0x74, 0x75,
    0x73, 0x74, 0x75, 0x76, 0x74, 0x75, 0x76, 0x77,
    0x75, 0x76, 0x77, 0x78, 0x76, 0x77, 0x78, 0x79,
    0x77, 0x78, 0x79, 0x7A, 0x78, 0x79, 0x7A, 0x7B,
])

MAGIC = b"EveryonePiano"
PPQ = 480


class EOPError(Exception):
    pass


def u16(data, off):
    return struct.unpack_from("<H", data, off)[0]


def u32(data, off):
    return struct.unpack_from("<I", data, off)[0]


def f64(data, off):
    return struct.unpack_from("<d", data, off)[0]


def decode_eop(raw):
    if len(raw) < 0x1BC:
        raise EOPError("arquivo muito pequeno para ser um EOP válido")

    # EOP v200 possui um NUL final não criptografado.
    payload = raw[:-1] if raw and raw[-1] == 0 else raw

    decoded = bytearray(len(payload))
    for i, b in enumerate(payload):
        decoded[i] = b ^ XOR_MASK[i % 32]

    if bytes(decoded[:13]) != MAGIC:
        raise EOPError(
            "assinatura inválida: o arquivo não parece ser uma partitura "
            "Everyone Piano compatível"
        )

    return bytes(decoded)


def decode_text(raw):
    if not raw:
        return ""

    raw = raw.split(b"\0", 1)[0]

    for enc in ("utf-8", "gbk", "cp936", "big5"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError:
            pass

    return raw.decode("utf-8", errors="replace").strip()


def read_header(decoded):
    version = u32(decoded, 0x10)
    numerator = u32(decoded, 0x14)
    denominator = u32(decoded, 0x18)
    tempo = u32(decoded, 0x1C)

    title = decode_text(decoded[0x134:0x174])
    author = decode_text(decoded[0x174:0x1B4])

    if tempo <= 0:
        tempo = 120

    return {
        "version": version,
        "numerator": numerator,
        "denominator": denominator,
        "tempo": tempo,
        "title": title,
        "author": author,
    }


def parse_v200(decoded, header):
    block_count = u32(decoded, 0x20)

    if not 1 <= block_count <= 4:
        raise EOPError(
            f"EOP 2.00: número de blocos inválido ({block_count})"
        )

    mapping_start = 0x1B8 + (block_count - 1) * 0x184
    record_start = mapping_start + 28
    event_start = record_start + 255 * 12 + 28

    if event_start > len(decoded):
        raise EOPError("EOP 2.00: tabela de mapeamento ultrapassa o arquivo")

    left_velocity = u32(decoded, mapping_start + 12)
    right_velocity = u32(decoded, mapping_start + 16)

    if left_velocity > 127:
        raise EOPError("EOP 2.00: velocity da mão esquerda inválida")
    if right_velocity > 127:
        raise EOPError("EOP 2.00: velocity da mão direita inválida")

    # scan code -> (MIDI note, hand)
    mappings = {}

    for i in range(255):
        off = record_start + i * 12
        scan_code, action, note = struct.unpack_from("<III", decoded, off)

        if scan_code != i + 1:
            raise EOPError(
                f"EOP 2.00: registro {i + 1} tem scan code {scan_code}"
            )

        # 1 = direita, 0x00010001 = esquerda
        if action == 1:
            if note <= 127:
                mappings[scan_code] = (note, "right", right_velocity)
        elif action == 0x00010001:
            if note <= 127:
                mappings[scan_code] = (note, "left", left_velocity)

    remaining = len(decoded) - event_start

    if remaining < 16 or remaining % 16 != 0:
        raise EOPError(
            "EOP 2.00: área de eventos não possui registros de 16 bytes"
        )

    record_count = remaining // 16
    terminator = None

    for i in range(record_count):
        off = event_start + i * 16
        if decoded[off + 8] == 0:
            terminator = i
            break

    if terminator is None:
        raise EOPError("EOP 2.00: terminador dos eventos não encontrado")

    events = []

    for i in range(terminator):
        off = event_start + i * 16

        timestamp = f64(decoded, off)
        status = decoded[off + 8]
        scan_code = decoded[off + 9]
        velocity = decoded[off + 10]

        if not math.isfinite(timestamp) or timestamp < 0:
            raise EOPError(f"EOP 2.00: timestamp inválido no evento {i}")

        if status not in (0x80, 0x90):
            raise EOPError(
                f"EOP 2.00: status inválido 0x{status:02X} no evento {i}"
            )

        if any(decoded[off + j] != 0 for j in range(11, 16)):
            raise EOPError(
                f"EOP 2.00: bytes reservados inválidos no evento {i}"
            )

        if scan_code not in mappings:
            # Teclas de controle não devem gerar MIDI.
            continue

        note, hand, mapped_velocity = mappings[scan_code]

        # Em EOP 2.00 a gravação normalmente deixa velocity do evento em
        # zero; o valor real da mão fica no cabeçalho da tabela.
        if status == 0x90:
            velocity = mapped_velocity

        events.append({
            "time_ms": timestamp,
            "status": status,
            "note": note,
            "velocity": max(0, min(127, velocity)),
            "hand": hand,
            "channel": 0 if hand == "left" else 1,
        })

    return events


def parse_v201_v301(decoded, header):
    """
    Implementação do layout comum documentado para EOP 2.01/3.01.

    Nessas versões o mapping identifica a tecla e a nota, mas não fornece
    a mesma distinção esquerda/direita existente no v200.
    """
    version = header["version"]
    record_size = 42 if version == 201 else 52

    first_section_size = u32(decoded, 0x1B8)

    # Layout comum: [u32 tamanho][seção][u32 tamanho][seção]...
    if first_section_size != 0:
        container_size = u32(decoded, 0x28)

        if container_size == 0:
            container_size = 4 + first_section_size

        container_end = 0x1B8 + container_size

        if container_size < 4 or container_end > len(decoded):
            raise EOPError("container de mapeamento inválido")

        mappings = {}
        cursor = 0x1B8

        while cursor < container_end:
            if cursor + 4 > container_end:
                raise EOPError("seção de mapeamento truncada")

            section_size = u32(decoded, cursor)
            section_start = cursor + 4

            if (
                section_size < 28
                or section_start + section_size > container_end
                or (section_size - 28) % record_size != 0
            ):
                raise EOPError("tamanho de seção de mapeamento inválido")

            parse_mapping_records(
                decoded, section_start, section_size, record_size, mappings
            )

            cursor = section_start + section_size

        event_start = container_end

    else:
        # Variante v201 com primeiro comprimento zero.
        mapping_container_size = u32(decoded, 0x28)
        event_container_size = u32(decoded, 0x2C)

        if mapping_container_size < 4:
            raise EOPError("container de mapeamento v201 inválido")

        if (
            event_container_size < 16
            or event_container_size % 16 != 0
            or event_container_size > len(decoded)
        ):
            raise EOPError("container de eventos v201 inválido")

        event_start = len(decoded) - event_container_size
        mapping_start = event_start - (mapping_container_size - 4)

        if mapping_start < 0:
            raise EOPError("posição do mapeamento v201 inválida")

        # A variante zero-section pode possuir a primeira seção sem prefixo.
        found = None

        first_size = 28
        while first_size <= event_start - mapping_start:
            try:
                temp = {}
                parse_mapping_records(
                    decoded, mapping_start, first_size, record_size, temp
                )

                cursor = mapping_start + first_size

                while cursor < event_start:
                    if cursor + 4 > event_start:
                        raise EOPError("seção adicional truncada")

                    size = u32(decoded, cursor)
                    start = cursor + 4

                    if (
                        size < 28
                        or start + size > event_start
                        or (size - 28) % record_size != 0
                    ):
                        raise EOPError("seção adicional inválida")

                    parse_mapping_records(
                        decoded, start, size, record_size, temp
                    )
                    cursor = start + size

                if cursor == event_start:
                    if found is not None:
                        raise EOPError(
                            "layout v201 ambíguo; mais de uma segmentação válida"
                        )
                    found = temp
            except EOPError:
                pass

            first_size += record_size

        if found is None:
            raise EOPError("nenhuma segmentação válida de mapeamento v201")

        mappings = found

    if event_start > len(decoded):
        raise EOPError("início dos eventos fora do arquivo")

    remaining = len(decoded) - event_start

    if remaining < 16 or (remaining - 16) % 16 != 0:
        raise EOPError("área de eventos v201/v301 inválida")

    count = (remaining - 16) // 16

    events = []

    for i in range(count):
        off = event_start + i * 16

        timestamp = f64(decoded, off)
        status = decoded[off + 8]
        scan_code = decoded[off + 9]
        velocity = decoded[off + 10]

        if not math.isfinite(timestamp) or timestamp < 0:
            raise EOPError(f"timestamp inválido no evento {i}")

        if status not in (0x80, 0x90):
            raise EOPError(
                f"status inválido 0x{status:02X} no evento {i}"
            )

        if any(decoded[off + j] != 0 for j in range(11, 16)):
            raise EOPError(f"bytes reservados inválidos no evento {i}")

        notes = mappings.get(scan_code)

        if notes is None:
            # Sem mapeamento, não há como saber a nota.
            continue

        # mapping v201/v301 pode teoricamente ter múltiplas notas para
        # uma mesma tecla.
        for note in notes:
            events.append({
                "time_ms": timestamp,
                "status": status,
                "note": note,
                "velocity": velocity,
                "hand": "piano",
                "channel": 0,
            })

    return events


def parse_mapping_records(decoded, section_start, section_size,
                          record_size, mappings):
    records = (section_size - 28) // record_size

    for i in range(records):
        off = section_start + 28 + i * record_size

        scan_code = decoded[off + 4]
        action = u16(decoded, off + 32)
        note = u16(decoded, off + 34)

        if action == 0x0090:
            if note > 127:
                raise EOPError(
                    f"nota MIDI inválida {note} no mapeamento"
                )

            mappings.setdefault(scan_code, set()).add(note)
        else:
            # Control mapping: a tecla existe, mas não produz nota.
            mappings.setdefault(scan_code, set())

    # Converter sets em listas ordenadas.
    for k in list(mappings):
        mappings[k] = sorted(mappings[k])


def parse_eop(raw):
    decoded = decode_eop(raw)
    header = read_header(decoded)

    if header["version"] == 200:
        events = parse_v200(decoded, header)
    elif header["version"] in (201, 301):
        events = parse_v201_v301(decoded, header)
    else:
        raise EOPError(
            f"versão EOP não suportada: {header['version']}"
        )

    # Os eventos do EOP são absolutos e devem ser monotônicos.
    last = -1.0
    for e in events:
        if e["time_ms"] < last:
            raise EOPError("eventos EOP fora de ordem temporal")
        last = e["time_ms"]

    return header, events


def vlq(value):
    """MIDI variable-length quantity."""
    value = max(0, int(value))
    buffer = value & 0x7F

    out = bytearray()

    while True:
        value >>= 7
        if value:
            buffer <<= 8
            buffer |= (value & 0x7F) | 0x80
        else:
            break

    while True:
        out.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break

    return bytes(out)


def ms_to_ticks(ms, bpm):
    # 480 ticks por semínima.
    return int(round((ms * bpm * PPQ) / 60000.0))


def make_track(events, bpm, channel, name):
    """
    Cria uma pista MIDI usando timestamps absolutos convertidos em ticks.
    """
    midi_events = []

    # Nome da pista.
    track_name = name.encode("utf-8", errors="replace")[:127]
    meta_name = b"\xFF\x03" + bytes([len(track_name)]) + track_name

    # Evento de nome no tempo 0.
    midi_events.append((0, 0, meta_name))

    for e in events:
        if e["channel"] != channel:
            continue

        tick = ms_to_ticks(e["time_ms"], bpm)

        # Note-off antes de note-on no mesmo tick ajuda editores MIDI.
        priority = 0 if e["status"] == 0x80 else 1

        status = e["status"] | channel
        velocity = e["velocity"] if e["status"] == 0x90 else 0

        data = bytes([
            status,
            e["note"] & 0x7F,
            velocity & 0x7F,
        ])

        midi_events.append((tick, priority, data))

    midi_events.sort(key=lambda x: (x[0], x[1]))

    track = bytearray()
    previous_tick = 0

    for tick, _, data in midi_events:
        delta = tick - previous_tick
        if delta < 0:
            delta = 0

        track += vlq(delta)
        track += data
        previous_tick = tick

    track += b"\x00\xFF\x2F\x00"

    return b"MTrk" + struct.pack(">I", len(track)) + track


def make_tempo_track(header, bpm):
    track = bytearray()

    name = b"EOP Tempo"
    track += b"\x00\xFF\x03" + bytes([len(name)]) + name

    # Tempo em microssegundos por semínima.
    mpqn = int(round(60000000 / bpm))
    mpqn = max(1, min(0xFFFFFF, mpqn))

    track += b"\x00\xFF\x51\x03"
    track += mpqn.to_bytes(3, "big")

    # Compasso.
    numerator = max(1, min(255, header.get("numerator", 4)))
    denominator = max(1, header.get("denominator", 4))

    # EOP guarda o denominador como 4, 8, etc.
    # MIDI usa log2(denominador).
    power = 0
    d = denominator
    while d > 1 and d % 2 == 0:
        power += 1
        d //= 2

    if d != 1:
        power = 2

    track += b"\x00\xFF\x58\x04"
    track += bytes([numerator, power, 24, 8])

    track += b"\x00\xFF\x2F\x00"

    return b"MTrk" + struct.pack(">I", len(track)) + track


def write_midi_format1(header, events, output_path):
    bpm = header["tempo"]

    left = [e for e in events if e["hand"] == "left"]
    right = [e for e in events if e["hand"] == "right"]

    # Para versões que não têm informação de mão:
    piano = [
        e for e in events
        if e["hand"] not in ("left", "right")
    ]

    tracks = []

    tracks.append(make_tempo_track(header, bpm))

    if left or right:
        tracks.append(make_track(left, bpm, 0, "Mao Esquerda"))
        tracks.append(make_track(right, bpm, 1, "Mao Direita"))
    else:
        tracks.append(make_track(piano, bpm, 0, "Piano"))

    midi_header = (
        b"MThd" +
        struct.pack(">IHHH", 6, 1, len(tracks), PPQ)
    )

    with open(output_path, "wb") as f:
        f.write(midi_header)
        for track in tracks:
            f.write(track)


def convert_file(path):
    path = Path(path)

    if path.suffix.lower() != ".eop":
        raise EOPError("o arquivo não possui extensão .EOP")

    raw = path.read_bytes()
    header, events = parse_eop(raw)

    output = path.with_suffix(".mid")

    # Evita sobrescrever silenciosamente.
    if output.exists():
        stem = path.stem
        n = 2
        while True:
            candidate = path.with_name(f"{stem}_converted_{n}.mid")
            if not candidate.exists():
                output = candidate
                break
            n += 1

    write_midi_format1(header, events, output)

    left_count = sum(
        1 for e in events if e["hand"] == "left" and e["status"] == 0x90
    )
    right_count = sum(
        1 for e in events if e["hand"] == "right" and e["status"] == 0x90
    )
    piano_count = sum(
        1 for e in events
        if e["hand"] not in ("left", "right") and e["status"] == 0x90
    )

    print()
    print("=" * 64)
    print("EOP -> MIDI concluído")
    print("=" * 64)
    print(f"Arquivo : {path.name}")
    print(f"Versão  : {header['version'] / 100:.2f}")
    print(f"Título  : {header['title'] or '(sem título)'}")
    print(f"Autor   : {header['author'] or '(desconhecido)'}")
    print(f"BPM     : {header['tempo']}")
    print(f"Eventos : {len(events)}")
    print(f"Notas E : {left_count}")
    print(f"Notas D : {right_count}")
    if piano_count:
        print(f"Notas   : {piano_count}")
    print(f"MIDI    : {output}")
    print("=" * 64)

    return output


def main():
    # Arrastar arquivos para um .py no Windows entrega os caminhos em argv.
    files = sys.argv[1:]

    # Permite também arrastar arquivos sobre o executável convertido com
    # PyInstaller.
    if not files:
        print("EOP -> MIDI")
        print()
        print("Arraste um arquivo .EOP sobre este programa.")
        print("Ou execute:")
        print("  python eop_to_midi.py arquivo.eop")
        print()
        input("Pressione ENTER para sair...")
        return

    success = 0
    failures = 0

    for filename in files:
        try:
            convert_file(filename)
            success += 1
        except Exception as exc:
            failures += 1
            print()
            print("ERRO ao converter:", filename)
            print(" ", exc)

    print()
    print(f"Finalizado: {success} convertido(s), {failures} erro(s).")

    if failures:
        print()
        print("Se algum arquivo for uma versão EOP diferente ou corrompida,")
        print("envie esse arquivo para que o parser possa ser ajustado.")

    input("\nPressione ENTER para fechar...")


if __name__ == "__main__":
    main()
