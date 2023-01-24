curl -L http://cpanmin.us | perl - App::cpanminus

if [ ! -d defects4j ]; then
  git clone https://github.com/rjust/defects4j.git
fi
cd defects4j
cpanm --installdeps .

./init.sh
export PATH=$PATH:$PWD/framework/bin
