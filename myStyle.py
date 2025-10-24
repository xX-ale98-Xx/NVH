import ttkbootstrap as ttkb

def myStyles():
    # Initialize the style
    style = ttkb.Style()

    # Frame styles - utilizzati nell'UI
    style.configure('TFrame', background='#F1F1F1')
    style.configure('headerFrame.TFrame', background='#ffe0b3')

    # Header styles - utilizzati nell'UI  
    style.configure('headerLabel.TLabel', background='#ffe0b3')

    # Label styles - utilizzati nell'UI  
    style.configure("Big.TLabelframe.Label", font=("Inter", 12, "bold"))

    # Label styles - utilizzati nell'UI  
    style.configure("bigTextButton.Button", font=("Inter", 12))

    # IMPORTANT: Reset default TButton style to prevent blue halos on matplotlib toolbar buttons
    style.configure('TButton', 
                    relief='raised',
                    padding=(6, 3))
    style.map('TButton',
              background=[],
              foreground=[])

    return style