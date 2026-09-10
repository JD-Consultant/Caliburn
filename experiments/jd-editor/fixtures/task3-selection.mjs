import { createJdEditor } from '../native/dist/profile.js';
const value=[{id:'repeat',type:'p',children:[{text:'同文同文'}]}];
const editor=createJdEditor(value);
editor.tf.select({anchor:{path:[0,0],offset:2},focus:{path:[0,0],offset:4}});
process.stdout.write(JSON.stringify({value,range:editor.selection}));
