import pandas as pd
import os 
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
import wittgenstein as lw # Biblioteca para o RIPPER
import kagglehub


path = kagglehub.dataset_download("pavansubhasht/ibm-hr-analytics-attrition-dataset")
csv_file = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.csv')][0]
df = pd.read_csv(csv_file)

df['Attrition'] = df['Attrition'].map({'Yes': 1, 'No': 0})

colunas_inuteis = ['EmployeeCount', 'EmployeeNumber', 'Over18', 'StandardHours']
df = df.drop(columns=colunas_inuteis)

X = df.drop(columns=['Attrition'])
y = df['Attrition']

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.3, random_state=42, stratify=y
)

# treino do Algoritmo 
modelo_regras = lw.RIPPER(random_state=42)
modelo_regras.fit(X_train, y_train)

# extração e Avaliação
print("Base de Regras Geradas pelo RIPPER")
modelo_regras.out_model()

y_pred = modelo_regras.predict(X_test)

print("\n Métricas de Desempenho")
print(f"Acurácia:  {accuracy_score(y_test, y_pred):.4f}")
print(f"Precisão:  {precision_score(y_test, y_pred):.4f}")
print(f"Recall:    {recall_score(y_test, y_pred):.4f}")
print(f"F1-Score:  {f1_score(y_test, y_pred):.4f}")

y_pred = [int(p) for p in y_pred]  
cm = confusion_matrix(y_test, y_pred, labels=[0, 1])
tn, fp, fn, tp = cm.ravel()

print("\nMATRIZ DE CONFUSÃO (TESTE)")
print(f"Verdadeiros Negativos (Real Fica, Previsto Fica) : {tn}")
print(f"Falsos Positivos (Real Fica, Previsto Sai) : {fp}")
print(f"Falsos Negativos (Real Sai, Previsto Fica) : {fn}")
print(f"Verdadeiros Positivos (Real Sai, Previsto Sai) : {tp}")