import requests
from openai import OpenAI
import json
import chainlit as cl
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import uuid

# Cấu hình OpenAI
gpt = OpenAI(
    organization= os.getenv("ORG_ID"),
    api_key=os.getenv("OPENAI_API_KEY"),
    project=os.getenv("PROJECT_ID"),
)

ASSISTANT_ID = os.getenv("ASSISTANT_ID")

# SMTP Configuration for Email Sending
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

global_show_qr = False


tools = [
    {
        "type": "function",
        "function": {
            "name": "Booking",
            "description": "Dùng để cho khách hàng đặt chỗ, đặt tour du lịch và trả về mã đặt tour.",
            "parameters": {
                "type": "object",
                "properties": {
                    "Ten_khach_hang": {
                        "type": "string",
                        "description": "Tên của khách hàng đặt chỗ."
                    },
                    "Ten_tour": {
                        "type": "string",
                        "description": "Tên tour du lịch mà khách hàng muốn đặt."
                    },
                    "so_nguoi": {
                        "type": "string",
                        "format": "number",
                        "description": "Tổng số người đi tour."
                    },
                    "gia_tien": {
                        "type": "string",
                        "format": "number",
                        "description": "Giá tour cho 1 người."
                    },
                    "Ngay_dat": {
                        "type": "string",
                        "format": "date",
                        "description": "Ngày đặt tour du lịch."
                    },
                    
                },
                "required": [
                    "Ten_khach_hang",
                    "Ten_tour",
                    "Ngay_dat",
                    "so_nguoi",
                    "gia_tien"
                ]
            }
        }
    },
    {
    "type": "function",
    "function": {
        "name": "TimTour",
        "description": "Được sử dụng để tìm và đặt tour cho khách hàng bằng cách tìm kiếm trong các tệp thông tin tour được chỉ định. Các phương thức thanh toán bao gồm chuyển khoản ngân hàng, chuyển khoản qua ví điện tử Momo và chuyển khoản qua ví điện tử Zalo Pay. Luôn tạo mã QR cho khách hàng.",
        "parameters": {
            "type": "object",
            "properties": {
                "TourName": {
                    "type": "string",
                    "description": "The name of the tour that the customer wants to book."
                },

                "TourInfoFile": {
                    "type": "string",
                    "enum": [
                        "Nha_Trang.txt",
                        "Ha_Noi.txt",
                        "Da_Nang.txt"
                    ],
                    "description": "Select the file containing detailed information about the tour. Each file offers comprehensive insights and highlights of the tour destination, ensuring you get exactly what you need for a perfect travel experience."
                }

            },
            "required": [
                "TourName",
                "TourInfoFile"
            ]
        }
    },
},
{
    "type": "function",
    "function": {
        "name": "HoTro",
        "description": "Sử dụng để nhận nội dung cần hỗ trợ và email từ khách hàng, sau đó gửi thông tin này đến email của bộ phận hỗ trợ. Khách hàng cần cung cấp nội dung cần hỗ trợ và địa chỉ email liên hệ.",
        "parameters": {
            "type": "object",
            "properties": {
                "NoiDungHoTro": {
                    "type": "string",
                    "description": "Nội dung mà khách hàng cần hỗ trợ."
                    },
                "EmailKhachHang": {
                    "type": "string",
                    "description": "Địa chỉ email của khách hàng để liên hệ."
                }
            },
            "required": [
                "NoiDungHoTro",
                "EmailKhachHang"
            ]
        }
    }
},
{
    "type": "function",
    "function": {
        "name": "GenerateQR",
        "description": "Gọi function này sau khi đặt tour thành công hoặc khách hàng yêu cầu thanh toán tour đã đặt. Tạo mã QR để thanh toán ngân hàng cho khách hàng với tour đã đặt. Hãy nói tổng số tiền khách cần thanh toán, thông tin chi tiết đặt tour và mã đặt tour.",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id": {
                    "type": "string",
                    "description": "Mã đặt chỗ duy nhất của khách hàng."
                },
                "payment_method": {
                    "type": "string",
                    "description": "Chuyển khoản ngân hàng."
                }
            },
            "required": [
                "booking_id",
                "payment_method"
            ]
        }
    }
}

]


# Send email function
def send_email(from_addr, to_addr, subject, body):
    message = MIMEMultipart()
    message['From'] = from_addr
    message['To'] = to_addr
    message['Subject'] = subject
    message.attach(MIMEText(body, 'plain'))
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(SMTP_USERNAME, SMTP_PASSWORD)
    server.sendmail(from_addr, to_addr, message.as_string())
    server.quit()

# Support Function
def HoTro(NoiDungHoTro, EmailKhachHang):
    noi_dung_staff = f"Support request: {NoiDungHoTro}\nFrom: {EmailKhachHang}"
    send_email(SMTP_USERNAME, 'nhattruong@aihoply.com', 'Hỗ Trợ Khách Hàng', noi_dung_staff)

    noi_dung_client = f"Kính gửi khách hàng,\n\nYêu cầu hỗ trợ của bạn đã được nhận:\n{NoiDungHoTro}\n\nCảm ơn bạn,\nĐội ngũ hỗ trợ"
    send_email(SMTP_USERNAME, EmailKhachHang, 'Xác Nhận Yêu Cầu Hỗ Trợ', noi_dung_client)
    return "Support ticket created, please check your mail box."


def TimTour(TourName, TourInfoFile):
    with open(TourInfoFile, "r",encoding="utf-8") as file:
        tour=file.read()
    return tour


def Booking(Ten_khach_hang, Ten_tour, so_nguoi, gia_tien, Ngay_dat):
    # Tạo mã đặt chỗ duy nhất
    booking_id = str(uuid.uuid4())
    
    # Tính tổng số tiền
    tong_tien = int(so_nguoi) * int(gia_tien)
    
    # Tạo chuỗi chứa thông tin đặt chỗ
    booking_details = (
        f"Booking ID: {booking_id}\n"
        f"Tên khách hàng: {Ten_khach_hang}\n"
        f"Tên tour: {Ten_tour}\n"
        f"Số người: {so_nguoi}\n"
        f"Giá tiền mỗi người: {gia_tien}\n"
        f"Tổng tiền: {tong_tien}\n"
        f"Ngày đặt: {Ngay_dat}\n"
        f"Trạng thái: Thành công"
    )
    
    return booking_details


# async def GenerateQR():
#     if os.path.exists("bank_qr_code.jpg"):
#         image = cl.Image(path="./bank_qr_code.jpg", name="image1", display="inline")
#         await cl.Message(
#             content="Mã QR thanh toán",
#             elements=[image],
#         ).send()
#         message_history = cl.user_session.get("message_history")
#         message_history.append({"role": "system", "content": "Payment QR sent."})
#     else:
#         print("QR image not found")
#         message_history = cl.user_session.get("message_history")
#         message_history.append({"role": "system", "content": "Payment QR generate failed."})


def GenerateQR(booking_id, payment_method):
    global global_show_qr
    global_show_qr = True
    return "Payment QR sent."


@cl.action_callback("verify_payment")
async def on_action(action: cl.Action):
    message_history = cl.user_session.get("message_history") or []
    message_history.append({"role": "system", "content": "User đã thanh toán đầy đủ số tiền đặt tour"})
    cl.user_session.set("message_history", message_history)
    
    query = "Bạn đã Thanh toán thành công chúc mừng bạn"
    msg = cl.Message(content="")
    stream = await creat_new_conversation(query)
    await process_stream(stream, msg)
    await msg.update()
    await cl.Message(content="Đặt tour thành công ✅").send()


async def add_verify_payment():
    await cl.Message(content="Nút xác thực thanh toán", actions=[
        cl.Action(name="verify_payment", value="verify_payment", description="Click me!")
    ]).send()


@cl.on_chat_start
def start_chat():
    if not cl.user_session.get("GLOBAL_THREAD_ID"):
        new_thread = gpt.beta.threads.create()
        cl.user_session.set("GLOBAL_THREAD_ID", new_thread.id)
    cl.user_session.set(
        "message_history",
        [{"role": "system", "content": "Bạn là 1 hướng dẫn viên đặt Tour, trợ giúp người du lịch. Hỗ trợ thông tour, đặt Tour, thanh toán."}],
    )


@cl.on_message
async def main(message: cl.Message):
    global global_show_qr
    message_history = cl.user_session.get("message_history")
    message_history.append({"role": "user", "content": message.content})

    msg = cl.Message(content="")
    await msg.send()
    query = message.content
    stream = await creat_new_conversation(query)
    await process_stream(stream, msg)
    message_history.append({"role": "assistant", "content": msg.content})
    await msg.update()

    if global_show_qr:
        # Open the image file in binary mode and read its contents
        image = cl.Image(path="./bank_qr_code.jpg", name="image1", display="inline")
        await cl.Message(
            content="Mã QR thanh toán",
            elements=[image],
        ).send()
        await add_verify_payment()
        global_show_qr = False


def calling_function_parallel(func_list):
    results = []
    for d in func_list:
        result = call_function_by_name_with_args(d['name'], d['arguments'], d['tool_call_id'])
        results.append(result)
    return results

def call_function_by_name_with_args(func_name, args_json, tool_call_id):
    args = json.loads(args_json)
    if func_name in globals() and callable(globals()[func_name]):
        output = globals()[func_name](**args)
        return {"tool_call_id": tool_call_id, "output": output}
    else:
        return {"tool_call_id": tool_call_id, "output": f"Function '{func_name}' not found."}

def handle_function_call_event(event):
    actions = event.data.required_action.submit_tool_outputs.tool_calls
    func_list = []
    for action in actions:
        if action.type == 'function':
            function_name = action.function.name
            function_args = action.function.arguments
            call_id = action.id
            function_item = {
                "name": function_name,
                "arguments": function_args,
                "tool_call_id": call_id
            }
            func_list.append(function_item)
    tool_outputs = calling_function_parallel(func_list)
    return tool_outputs

async def process_stream(stream, msg, parent_thread_id=None):
    thread_id = cl.user_session.get("GLOBAL_THREAD_ID")
    run_id = ''
    for event in stream:
        event_type = event.event

        if event_type == 'thread.run.requires_action':
            run_id = event.data.id
        await process_event(event, msg, thread_id, run_id)

async def process_event(event, msg, thread_id='', run_id=''):
    event_type = event.event

    if event_type == 'thread.run.requires_action':
        tool_outputs = handle_function_call_event(event)
        run_after_function_calling = gpt.beta.threads.runs.submit_tool_outputs(
            thread_id=thread_id,
            run_id=run_id,
            tool_outputs=tool_outputs,
            stream=True
        )
        await process_stream(run_after_function_calling, msg, parent_thread_id=thread_id)

    elif event_type == 'thread.message.delta':
        message_content = event.data.delta.content[0].text.value
        await msg.stream_token(message_content)

async def creat_new_conversation(query):
    thread_id = cl.user_session.get("GLOBAL_THREAD_ID")
    
    openai_message = gpt.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=query
    )
    
    stream = gpt.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=ASSISTANT_ID,
        tools=tools,
        stream=True
    )
    return stream

if __name__ == '__main__':
    cl.launch()