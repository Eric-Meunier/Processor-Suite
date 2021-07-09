for %%f in (*.ui) do (
          pyside2-uic "%%~nf.ui" -o "%%~nf.py"
		  echo %%f
)

