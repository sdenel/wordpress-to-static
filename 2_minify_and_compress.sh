#!/usr/bin/env bash
set -e

DIR="www/"

# install nodejs:
# sudo curl -o /usr/local/bin/n https://raw.githubusercontent.com/visionmedia/n/master/bin/n
# chmod +x /usr/local/bin/n
# n stable
# npm install -g html-minifier uglify-js clean-css-cli

# TODO: https://github.com/tdewolff/minify might be a good alternative

for file in `find $DIR -type f | grep .html | grep -v .gz`; do
    mv "$file" "$file.legacy"
    html-minifier --collapse-whitespace --remove-comments --remove-optional-tags --remove-redundant-attributes --remove-script-type-attributes --remove-tag-whitespace --use-short-doctype "$file.legacy" -o "$file"
    OLD_SIZE=`stat --printf="%s" "$file.legacy"`
    NEW_SIZE=`stat --printf="%s" "$file"`
    echo "html-minifier: $file: $OLD_SIZE -> $NEW_SIZE"
    rm "$file.legacy"
done

for file in `find $DIR -type f | grep .css | grep -v .gz`; do
    mv "$file" "$file.legacy"
    cleancss -o "$file" "$file.legacy"
    OLD_SIZE=`stat --printf="%s" "$file.legacy"`
    NEW_SIZE=`stat --printf="%s" "$file"`
    echo "cleancss: $file: $OLD_SIZE -> $NEW_SIZE"
    rm "$file.legacy"
done

for file in `find $DIR -type f | grep .js | grep -v .gz`; do
    mv "$file" "$file.legacy"
    uglifyjs --compress --mangle -o "$file" -- "$file.legacy"
    OLD_SIZE=`stat --printf="%s" "$file.legacy"`
    NEW_SIZE=`stat --printf="%s" "$file"`
    echo "uglifyjs: $file: $OLD_SIZE -> $NEW_SIZE"
    rm "$file.legacy"
done

for file in `find $DIR -type f | grep -v .gz`; do
    gzip -9 -k -f -c "$file" > "$file.gz";
    OLD_SIZE=`stat --printf="%s" "$file"`
    NEW_SIZE=`stat --printf="%s" "$file.gz"`
    echo "gzip: $file: $OLD_SIZE -> $NEW_SIZE"
done
