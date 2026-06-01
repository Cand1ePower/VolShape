// 声明 CSS 模块，使 TypeScript 能够正确识别并编译 .css 文件的导入
declare module '*.module.css' {
  const classes: { [key: string]: string };
  export default classes;
}

declare module '*.css' {
  const content: any;
  export default content;
}
