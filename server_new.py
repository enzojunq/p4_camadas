import time
import datetime
import binascii
from enlace import *

serialName = "COM6"  # Altere para a porta correta
com2 = enlace(serialName)

EOP = b'\xAA\xBB\xCC'  # 3 bytes

def is_datagram_complete(data):
    """Verifica se o datagrama está completo (HEAD + EOP)"""
    return data[-3:] == EOP

def calculate_crc(payload):
    crc = binascii.crc_hqx(payload, 0xFFFF)
    return crc

def receive_file():
    """Recebe um arquivo fragmentado em pacotes"""
    all_data = bytearray()
    expected_packet = 1
    total_packets = None

    while True:
        datagram, _ = com2.getData(1024)  # Ajuste o tamanho do buffer conforme necessário
        
        if is_datagram_complete(datagram):
            head = datagram[:12]
            packet_number = int.from_bytes(head[0:2], 'big')
            total_packets = int.from_bytes(head[2:4], 'big') if total_packets is None else total_packets
            payload_size = int.from_bytes(head[4:6], 'big')
            crc_received = int.from_bytes(head[6:8], 'big')
            message_type = head[8]
            payload = datagram[12:-3]  # Exclui o EOP

            log_event('receb', message_type, len(datagram), packet_number, total_packets, crc_received)
            
            # Verificar se o pacote está fora de ordem
            if packet_number != expected_packet:
                print(f'Servidor: Erro na ordem dos pacotes. Esperado {expected_packet}, recebido {packet_number}')
                nack_datagram = create_nack_datagram(expected_packet)
                com2.sendData(nack_datagram)
                log_event('envio', 5, len(nack_datagram))
                continue  # Aguarda o reenvio do pacote correto

            # Verificar se o tamanho do payload é correto
            if len(payload) != payload_size:
                print(f'Servidor: Erro no tamanho do payload. Recebido {len(payload)}, esperado {payload_size}')
                nack_datagram = create_nack_datagram(expected_packet)
                com2.sendData(nack_datagram)
                log_event('envio', 5, len(nack_datagram))
                continue  # Aguarda o reenvio do pacote correto

            # Calcular o CRC do payload
            crc_calculated = calculate_crc(payload)
            if crc_received != crc_calculated:
                print(f'Servidor: Erro no CRC. Recebido {crc_received}, calculado {crc_calculated}')
                nack_datagram = create_nack_datagram(expected_packet)
                com2.sendData(nack_datagram)
                log_event('envio', 5, len(nack_datagram))
                continue  # Aguarda o reenvio do pacote correto

            # Se o pacote está correto, adiciona o payload e envia ACK
            all_data.extend(payload)
            print(f'Servidor: Pacote {packet_number}/{total_packets} recebido corretamente.')

            # Enviar ACK
            ack_datagram = create_ack_datagram(packet_number)
            com2.sendData(ack_datagram)
            log_event('envio', 4, len(ack_datagram))

            if packet_number == total_packets:
                print("Servidor: Todos os pacotes recebidos")
                break

            expected_packet += 1

    # Salvar o arquivo recebido
    with open('arquivo_recebido.txt', 'wb') as f:
        f.write(all_data)

def create_ack_datagram(packet_number):
    """Cria um datagrama ACK"""
    message_type = 4  # ACK
    head = (packet_number.to_bytes(2, 'big') +
            b'\x00'*6 +
            message_type.to_bytes(1, 'big') +
            b'\x00'*3)
    return head + EOP

def create_nack_datagram(expected_packet):
    """Cria um datagrama NACK solicitando o pacote correto"""
    message_type = 5  # NACK
    head = (expected_packet.to_bytes(2, 'big') +
            b'\x00'*6 +
            message_type.to_bytes(1, 'big') +
            b'\x00'*3)
    return head + EOP

def log_event(event_type, message_type, size, packet_number=None, total_packets=None, crc=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    with open('server_log.txt', 'a') as log_file:
        line = f"{timestamp} / {event_type} / {message_type} / {size}"
        if packet_number is not None and total_packets is not None and crc is not None:
            line += f" / {packet_number} / {total_packets} / {crc:04X}"
        log_file.write(line + "\n")

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
        datagram, _ = com2.getData(15)
        if is_datagram_complete(datagram):
            head = datagram[:12]
            message_type = head[8]
            log_event('receb', message_type, len(datagram))
            if message_type == 1:
                print("Servidor: Handshake recebido, pronto para receber arquivo")
                # Enviar resposta de handshake
                message_type = 2  # Handshake response
                response_head = b'\x00'*8 + message_type.to_bytes(1, 'big') + b'\x00'*3
                ack_datagram = response_head + EOP
                com2.sendData(ack_datagram)
                log_event('envio', message_type, len(ack_datagram))
                receive_file()
            else:
                print("Servidor: Mensagem recebida não é handshake")
        else:
            print("Servidor: Não recebeu handshake completo")

        com2.disable()

    except Exception as e:
        print("Servidor: Ocorreu um erro:", e)
        com2.disable()

if __name__ == "__main__":
    main()
