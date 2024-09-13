import time
import crcmod
import logging
from enlace import *

# Configuração da porta serial (altere para a porta correta)
serialName = "COM6"
com2 = enlace(serialName)

# Configurações do EOP
EOP = b'\xAA\xBB\xCC'  # 3 bytes

# Configuração do logger
logging.basicConfig(filename='server_log.txt', level=logging.INFO, format='%(message)s')

def calculate_crc(payload):
    """Calcula o CRC-16 do payload."""
    crc16_func = crcmod.mkCrcFun(0x18005, rev=False, initCrc=0xFFFF, xorOut=0x0000)
    crc = crc16_func(payload)
    return crc.to_bytes(2, byteorder='big')

def log_event(action, message_type, total_bytes, packet_number=None, total_packets=None, crc=None):
    """Registra um evento no arquivo de log."""
    timestamp = time.strftime('%d/%m/%Y %H:%M:%S.%f', time.localtime())
    log_line = f"{timestamp} / {action} / {message_type} / {total_bytes}"
    if packet_number is not None and total_packets is not None:
        log_line += f" / {packet_number} / {total_packets}"
    if crc is not None:
        log_line += f" / {crc.hex()}"
    logging.info(log_line)

def is_datagram_complete(data):
    """Verifica se o datagrama está completo (EOP no final)."""
    return data[-3:] == EOP

def receive_file():
    """Recebe um arquivo fragmentado em pacotes."""
    all_data = bytearray()
    expected_packet = 1
    total_packets = None

    while True:
        # Recebe o datagrama
        datagram, _ = com2.getData(1024)  # Ajuste o tamanho conforme necessário

        if is_datagram_complete(datagram):
            # Extrai os campos do cabeçalho
            packet_number = int.from_bytes(datagram[0:2], 'big')
            if total_packets is None:
                total_packets = int.from_bytes(datagram[2:4], 'big')
            payload_size = int.from_bytes(datagram[4:6], 'big')
            message_type = datagram[6]
            crc_received = datagram[8:10]
            payload = datagram[10:-3]  # Exclui o EOP

            # Log do recebimento
            log_event('receb', message_type, len(datagram), packet_number, total_packets, crc_received)

            # Verifica se o pacote está fora de ordem
            if packet_number != expected_packet:
                print(f'Servidor: Erro na ordem dos pacotes. Esperado {expected_packet}, recebido {packet_number}')
                com2.sendData(create_nack_datagram(expected_packet))
                log_event('envio', '6', 14)  # Tipo 6: NACK de erro de ordem
                continue  # Aguarda o reenvio do pacote correto

            # Verifica o tamanho do payload
            if len(payload) != payload_size:
                print(f'Servidor: Erro no tamanho do payload. Recebido {len(payload)}, esperado {payload_size}')
                com2.sendData(create_nack_datagram(expected_packet))
                log_event('envio', '6', 14)  # Tipo 6: NACK de erro de tamanho
                continue  # Aguarda o reenvio do pacote correto

            # Verifica o CRC
            crc_calculated = calculate_crc(payload)
            if crc_received != crc_calculated:
                print(f'Servidor: Erro de CRC no pacote {packet_number}.')
                com2.sendData(create_nack_datagram(expected_packet))
                log_event('envio', '5', 14)  # Tipo 5: NACK de erro de CRC
                continue  # Aguarda o reenvio do pacote

            # Se o pacote está correto, adiciona o payload e envia ACK
            all_data.extend(payload)
            print(f'Servidor: Pacote {packet_number}/{total_packets} recebido corretamente.')

            # Enviar ACK
            ack_datagram = create_ack_datagram(packet_number)
            com2.sendData(ack_datagram)
            log_event('envio', '4', len(ack_datagram))  # Tipo 4: ACK

            if packet_number == total_packets:
                print("Servidor: Todos os pacotes recebidos")
                break

            expected_packet += 1

    # Salvar o arquivo recebido
    with open('arquivo_recebido.txt', 'wb') as f:
        f.write(all_data)
    print("Servidor: Arquivo salvo com sucesso.")

def create_ack_datagram(packet_number):
    """Cria um datagrama ACK."""
    head = (
        packet_number.to_bytes(2, 'big') +
        b'\x00\x00' +  # Total de pacotes não é necessário
        b'\x00\x00' +  # Tamanho do payload
        b'\x04' +      # Tipo de mensagem: 4 (ACK)
        b'\x00'*3 +    # Reservado
        b'\x00\x00'    # CRC vazio
    )
    return head + EOP

def create_nack_datagram(expected_packet):
    """Cria um datagrama NACK solicitando o pacote correto."""
    head = (
        expected_packet.to_bytes(2, 'big') +
        b'\x00\x00' +  # Total de pacotes não é necessário
        b'\x00\x00' +  # Tamanho do payload
        b'\x06' +      # Tipo de mensagem: 6 (NACK)
        b'\x00'*3 +    # Reservado
        b'\x00\x00'    # CRC vazio
    )
    return head + EOP

def main():
    try:
        com2.enable()

        # Receber byte de sacrifício e limpar buffer
        print("Servidor: esperando 1 byte de sacrifício")
        rxBuffer, nRx = com2.getData(1)
        com2.rx.clearBuffer()
        time.sleep(0.1)

        print("Servidor: Aguardando handshake...\n")

        # Aguardar handshake do cliente
        datagram, _ = com2.getData(14)  # Ajuste o tamanho conforme necessário
        if is_datagram_complete(datagram):
            message_type = datagram[6]
            if message_type == 1:  # Tipo 1: Handshake
                print("Servidor: Handshake recebido, pronto para receber arquivo")
                log_event('receb', message_type, len(datagram))
                ack_datagram = create_ack_datagram(0)
                com2.sendData(ack_datagram)
                log_event('envio', '2', len(ack_datagram))  # Tipo 2: ACK de handshake

                receive_file()
        else:
            print("Servidor: Erro no handshake.")

        com2.disable()

    except Exception as e:
        print("Servidor: Ocorreu um erro:", e)
        com2.disable()

if __name__ == "__main__":
    main()
