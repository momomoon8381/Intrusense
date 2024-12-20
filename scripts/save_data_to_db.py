import os
import pandas as pd
from sqlalchemy import create_engine, inspect, text
from tkinter import Tk, filedialog
import numpy as np

def select_files():
    """
    파일 선택 대화 상자를 열어 CSV 파일들을 선택합니다.
    """
    root = Tk()
    root.withdraw()  # Tkinter 기본 GUI 숨기기
    root.attributes('-topmost', True)  # 최상단에 표시
    files = filedialog.askopenfilenames(
        title="CSV 파일을 선택하세요",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )
    if not files:
        print("선택된 파일이 없습니다. 작업을 종료합니다.")
        exit()
    root.destroy()  # Tk 객체 종료
    return files

def create_db_engine(user, password, host, port, database):
    """
    MySQL 데이터베이스 연결 엔진을 생성합니다.
    """
    connection_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
    return create_engine(connection_url)

def create_table(engine, table_name, columns):
    """
    주어진 칼럼들을 기반으로 테이블을 생성합니다.
    매개변수로 받은 columns를 동적으로 처리합니다.
    """
    # 각 칼럼에 대한 SQL 데이터 타입을 매핑
    column_definitions = []


    for column in columns:
        # 칼럼 이름에 백틱 추가
        column_name = f"`{column}`"
        
        # FileName은 VARCHAR로 설정
        if column == 'FileName':
            column_definitions.append(f"{column_name} VARCHAR(255)")
        # Label, source는 INT로 설정
        elif column == 'Label':
            column_definitions.append(f"{column_name} INT")
        # 나머지 숫자형 데이터는 FLOAT로 설정
        else:
            column_definitions.append(f"{column_name} FLOAT")
    
    # 테이블 생성 SQL 구문
    create_table_sql = f"""
    CREATE TABLE IF NOT EXISTS {table_name} (
        id INT AUTO_INCREMENT PRIMARY KEY,
        {', '.join(column_definitions)},
        source VARCHAR(255)
    );
    """
    
    # 테이블 생성 실행
    with engine.connect() as connection:
        connection.execute(text(create_table_sql))
    print(f"'{table_name}' 테이블이 생성되었습니다.")

def check_and_drop_table(engine, table_name, columns):
    """
    테이블이 이미 존재하는 경우, 삭제 여부를 사용자에게 묻고 처리합니다.
    """
    inspector = inspect(engine)
    if table_name in inspector.get_table_names():
        user_input = input(f"경고: '{table_name}' 테이블이 이미 존재합니다. 테이블을 삭제하고 데이터 삽입을 시작할까요? (y/n): ")
        if user_input.lower() == 'y':
            with engine.connect() as connection:
                connection.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
            print(f"'{table_name}' 테이블이 삭제되었습니다.")
            create_table(engine, table_name, columns)
        else:
            user_input = input(f"기존 테이블에 데이터를 추가할까요? (y/n): ")
            if user_input.lower() != 'y':
                print("작업을 종료합니다.")
                exit()

def save_label_mapping(engine, label_mapping, table_name):
    """
    라벨 매핑 정보를 데이터프레임으로 변환 후 데이터베이스에 저장합니다.
    """
    label_df = pd.DataFrame(label_mapping.items(), columns=['Label', 'Encoded Value'])
    label_df.to_sql(table_name, con=engine, if_exists='replace', index=False)
    print(f"라벨 매핑 정보가 '{table_name}' 테이블에 저장되었습니다.")


def process_and_save_csv_to_db(engine, data_files, columns, table_name, source_table_name, label_mapping):
    """
    CSV 파일을 읽고, 데이터 처리 후 데이터베이스에 저장합니다.
    무한대와 NaN 값은 0으로 대체합니다.
    """
    source_df = pd.DataFrame(columns=['Index', 'FileName'])  # 파일 정보를 저장할 데이터프레임

    for idx, file in enumerate(data_files, 1):
        df = pd.read_csv(file, low_memory=False)
        df.columns = df.columns.str.strip()  # 칼럼명 앞뒤 공백 제거

        # 칼럼명 확인
        if list(df.columns) != columns:
            print(f"경고: {file} 파일의 칼럼명이 정의된 칼럼과 일치하지 않습니다.")
            exit()

        # 무한대와 NaN 값을 0으로 대체
        df.replace([np.inf, -np.inf, np.nan], 0, inplace=True)

        # 'Label'을 인코딩된 값으로 변경
        df['Label'] = df['Label'].map(label_mapping)

        # 'source' 칼럼 추가
        df['source'] = idx

        # 데이터 저장
        df.to_sql(table_name, con=engine, if_exists='append', index=False)
        print(f"{file} 데이터베이스에 저장 완료")

        # 파일 정보 기록
        file_info = pd.DataFrame({'Index': [idx], 'FileName': [os.path.basename(file)]})
        source_df = pd.concat([source_df, file_info], ignore_index=True)

    # 파일 정보 저장
    source_df.to_sql(source_table_name, con=engine, if_exists='replace', index=False)
    print(f"파일 정보가 '{source_table_name}' 테이블에 저장되었습니다.")
